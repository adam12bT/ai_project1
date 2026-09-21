"""
The LLM judge: grades explanations against the labelling guide, and proves
(or disproves) that it's trustworthy.

Three things live here, matching the brief's "reliability report":
  1. score      -- grade a run's outputs against their gold checklists
  2. report     -- agreement with human labels + position bias + verbosity bias
  3. helpers used by both

Usage:
    python -m harness.judge score --results results/run_v1_dev.jsonl --out results/judged_v1_dev.jsonl
    python -m harness.judge report --calibration data/calibration_set.jsonl --out results/reliability_report.json
"""
from __future__ import annotations

import argparse
import json

import groq
from tqdm import tqdm

from harness import config
from harness.schema import JUDGE_TOOL, call_with_tool, read_jsonl, write_jsonl

JUDGE_SYSTEM_PROMPT_PATH = config.PROMPTS_DIR / "judge_v1.txt"

PAIRWISE_TOOL = {
    "name": "submit_pairwise_verdict",
    "description": "Pick which of two SQL explanations is better.",
    "input_schema": {
        "type": "object",
        "properties": {
            "winner": {"type": "string", "enum": ["A", "B", "tie"]},
            "reason": {"type": "string", "description": "One sentence on why."},
        },
        "required": ["winner", "reason"],
    },
}


def _judge_pair(client, system_prompt, query, checklist, explanation_a, explanation_b) -> str:
    """Returns 'A', 'B', or 'tie'."""
    user_content = (
        f"SQL query:\n```sql\n{query}\n```\n\n"
        f"What a correct explanation must cover:\n{checklist}\n\n"
        f"Explanation A:\n{explanation_a}\n\n"
        f"Explanation B:\n{explanation_b}\n\n"
        f"Which explanation is better?"
    )
    result = call_with_tool(
        client=client,
        model=config.JUDGE_MODEL,
        system=system_prompt,
        user_content=user_content,
        tool=PAIRWISE_TOOL,
        max_tokens=200,
    )
    return result.data["winner"]


def _judge_one(client, system_prompt, query, checklist, explanation) -> dict:
    user_content = (
        f"SQL query:\n```sql\n{query}\n```\n\n"
        f"What a correct explanation must cover:\n{checklist}\n\n"
        f"Candidate explanation to grade:\n{explanation}"
    )
    result = call_with_tool(
        client=client,
        model=config.JUDGE_MODEL,
        system=system_prompt,
        user_content=user_content,
        tool=JUDGE_TOOL,
        max_tokens=config.MAX_TOKENS_JUDGE,
    )
    return {
        "verdict": result.data["verdict"],
        "score": result.data["score"],
        "reason": result.data["reason"],
        "judge_input_tokens": result.input_tokens,
        "judge_output_tokens": result.output_tokens,
    }


def score(results_path: str, out_path: str) -> str:
    """Grade every row of a run against its gold checklist."""
    system_prompt = JUDGE_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    rows = read_jsonl(results_path)
    client = groq.Groq()

    out_rows = []
    for row in tqdm(rows, desc="Judging"):
        if row.get("error") or not row.get("explanation"):
            out_rows.append({**row, "verdict": None, "score": None, "judge_reason": "skipped: no explanation"})
            continue
        verdict = _judge_one(client, system_prompt, row["query"], row.get("gold_checklist", ""), row["explanation"])
        out_rows.append({
            **row,
            "verdict": verdict["verdict"],
            "score": verdict["score"],
            "judge_reason": verdict["reason"],
            "judge_input_tokens": verdict["judge_input_tokens"],
            "judge_output_tokens": verdict["judge_output_tokens"],
        })

    write_jsonl(out_path, out_rows)
    print(f"Wrote {len(out_rows)} judged rows to {out_path}")
    return out_path


def _cohen_kappa(human: list[str], judge: list[str]) -> float:
    """Simple two-label Cohen's kappa for pass/fail agreement."""
    assert len(human) == len(judge)
    n = len(human)
    if n == 0:
        return float("nan")
    po = sum(1 for h, j in zip(human, judge) if h == j) / n
    labels = set(human) | set(judge)
    pe = 0.0
    for label in labels:
        p_h = sum(1 for h in human if h == label) / n
        p_j = sum(1 for j in judge if j == label) / n
        pe += p_h * p_j
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def _verbosity_pad(explanation: str) -> str:
    """Add filler that carries no additional information."""
    filler = (
        " To put it another way, this is essentially what is happening here, "
        "in general terms, when you consider the overall behavior of the query "
        "described above and think about it carefully."
    )
    return explanation + filler


def report(calibration_path: str, out_path: str) -> str:
    """
    Reliability report:
      - agreement between judge verdicts and human verdicts (+ Cohen's kappa)
      - position bias: not directly applicable to single-answer grading, so we
        instead check verdict stability by re-running the same item twice
      - verbosity bias: pad a passing explanation with content-free filler and
        see whether the score goes up
    """
    system_prompt = JUDGE_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    calib = read_jsonl(calibration_path)
    client = groq.Groq()

    human_labels, judge_labels, rows_out = [], [], []
    for item in tqdm(calib, desc="Calibrating against humans"):
        verdict = _judge_one(client, system_prompt, item["query"], item.get("gold_checklist", ""), item["explanation"])
        human_labels.append(item["human_verdict"])
        judge_labels.append(verdict["verdict"])
        rows_out.append({**item, "judge_verdict": verdict["verdict"], "judge_score": verdict["score"]})

    agreement_pct = round(
        100 * sum(1 for h, j in zip(human_labels, judge_labels) if h == j) / max(len(human_labels), 1), 1
    )
    kappa = round(_cohen_kappa(human_labels, judge_labels), 3)

    # Position bias: for items where we have both a passing and a failing
    # explanation of the SAME query, ask the judge to compare them, then
    # swap which slot (A/B) each one sits in and see if the "better" answer
    # still wins. A fair judge should always prefer the pass explanation
    # regardless of position.
    by_query = {}
    for item in calib:
        by_query.setdefault(item["query"], []).append(item)
    pairs = [
        (v[0], v[1]) if v[0]["human_verdict"] == "pass" else (v[1], v[0])
        for v in by_query.values()
        if len(v) >= 2 and {v[0]["human_verdict"], v[1]["human_verdict"]} == {"pass", "fail"}
    ]
    position_flips, n_pairs = 0, 0
    for good, bad in tqdm(pairs[:20], desc="Position bias check"):
        n_pairs += 1
        w1 = _judge_pair(client, system_prompt, good["query"], good.get("gold_checklist", ""), good["explanation"], bad["explanation"])
        w2 = _judge_pair(client, system_prompt, good["query"], good.get("gold_checklist", ""), bad["explanation"], good["explanation"])
        # good was A then B; a consistent judge picks "A" then "B" (i.e. always the good one)
        if not (w1 == "A" and w2 == "B"):
            position_flips += 1
    position_bias_rate = round(100 * position_flips / n_pairs, 1) if n_pairs else None

    # Stability check: re-grade a subsample twice, see how often the verdict flips.
    stability_sample = calib[: min(20, len(calib))]
    flips = 0
    for item in tqdm(stability_sample, desc="Stability re-check"):
        v1 = _judge_one(client, system_prompt, item["query"], item.get("gold_checklist", ""), item["explanation"])["verdict"]
        v2 = _judge_one(client, system_prompt, item["query"], item.get("gold_checklist", ""), item["explanation"])["verdict"]
        if v1 != v2:
            flips += 1
    stability_flip_rate = round(100 * flips / max(len(stability_sample), 1), 1)

    # Verbosity bias: only meaningful on items the judge already passed.
    passing_items = [r for r in rows_out if r["judge_verdict"] == "pass"][:20]
    score_ups = 0
    for item in tqdm(passing_items, desc="Verbosity bias check"):
        base = _judge_one(client, system_prompt, item["query"], item.get("gold_checklist", ""), item["explanation"])
        padded_explanation = _verbosity_pad(item["explanation"])
        padded = _judge_one(client, system_prompt, item["query"], item.get("gold_checklist", ""), padded_explanation)
        if padded["score"] > base["score"]:
            score_ups += 1
    verbosity_bias_rate = round(100 * score_ups / max(len(passing_items), 1), 1) if passing_items else None

    result = {
        "n_calibration_items": len(calib),
        "judge_human_agreement_pct": agreement_pct,
        "cohens_kappa": kappa,
        "verdict_stability_flip_rate_pct": stability_flip_rate,
        "verbosity_bias_rate_pct": verbosity_bias_rate,
        "position_bias_rate_pct": position_bias_rate,
        "n_position_bias_pairs": n_pairs,
        "notes": {
            "agreement": "Pct of calibration items where judge verdict == human verdict.",
            "kappa": "Chance-corrected agreement. <0.4 weak, 0.4-0.6 moderate, 0.6-0.8 substantial, >0.8 strong.",
            "stability": "Pct of a 20-item subsample where re-grading the SAME explanation flips the verdict. High = judge is noisy, not just biased.",
            "verbosity_bias": "Of items the judge already passed, pct whose score went UP after adding content-free filler. Should be near 0.",
            "position_bias": "Requires calibration_set.jsonl to contain a pass/fail pair per query (same 'query' value, one human_verdict=pass, one=fail). Pct of pairs where swapping which slot (A/B) the good explanation sits in changes which one the judge prefers. Should be near 0.",
        },
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))
    print(f"\nWrote reliability report to {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p_score = sub.add_parser("score")
    p_score.add_argument("--results", required=True)
    p_score.add_argument("--out", required=True)

    p_report = sub.add_parser("report")
    p_report.add_argument("--calibration", default=str(config.CALIBRATION_SET_PATH))
    p_report.add_argument("--out", required=True)

    args = parser.parse_args()
    if args.command == "score":
        score(args.results, args.out)
    elif args.command == "report":
        report(args.calibration, args.out)

