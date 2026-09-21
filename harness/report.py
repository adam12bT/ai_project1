"""
Turns a judged run (results/judged_.jsonl) into the numbers the report
needs: pass rate, score distribution, cost, latency. Never collapses
everything into one summary number — counts and percentages, per the brief.

Usage:
python -m harness.report summarize results/judged_v1_dev.jsonl
"""

from __future__ import annotations

import argparse
import json
import statistics

from harness import config
from harness.pricing import cost_usd
from harness.schema import read_jsonl


def summarize(judged_path: str) -> dict:
    rows = read_jsonl(judged_path)
    n = len(rows)

    graded = [
        r for r in rows
        if r.get("verdict") in ("pass", "fail")
    ]

    n_skipped = n - len(graded)

    n_pass = sum(
        1 for r in graded
        if r["verdict"] == "pass"
    )

    scores = [
        r["score"]
        for r in graded
        if r.get("score") is not None
    ]

    total_in = sum(
        r.get("input_tokens", 0) +
        r.get("judge_input_tokens", 0)
        for r in rows
    )

    total_out = sum(
        r.get("output_tokens", 0) +
        r.get("judge_output_tokens", 0)
        for r in rows
    )

    explainer_cost = cost_usd(
        config.EXPLAINER_MODEL,
        sum(r.get("input_tokens", 0) for r in rows),
        sum(r.get("output_tokens", 0) for r in rows),
    )

    judge_cost = cost_usd(
        config.JUDGE_MODEL,
        sum(r.get("judge_input_tokens", 0) for r in rows),
        sum(r.get("judge_output_tokens", 0) for r in rows),
    )

    latencies = [
        r["latency_s"]
        for r in rows
        if r.get("latency_s") is not None
    ]

    summary = {
        "run": judged_path,
        "n_items": n,
        "n_skipped_no_output": n_skipped,
        "n_pass": n_pass,
        "n_fail": len(graded) - n_pass,
        "pass_rate_pct": (
            round(100 * n_pass / len(graded), 1)
            if graded
            else None
        ),
        "mean_score": (
            round(statistics.mean(scores), 2)
            if scores
            else None
        ),
        "score_distribution": {
            str(s): scores.count(s)
            for s in sorted(set(scores))
        },
        "cost_usd": {
            "explainer": round(explainer_cost, 4),
            "judge": round(judge_cost, 4),
            "total": round(explainer_cost + judge_cost, 4),
            "per_1k_items_explainer_only": round(
                explainer_cost / max(n, 1) * 1000,
                2,
            ),
            "projected_at_100x_items": round(
                (explainer_cost + judge_cost) * 100,
                2,
            ),
        },
        "latency_s": {
            "mean": (
                round(statistics.mean(latencies), 3)
                if latencies
                else None
            ),
            "p95": (
                round(
                    sorted(latencies)[int(0.95 * len(latencies))],
                    3,
                )
                if latencies
                else None
            ),
        },
        "total_tokens": {
            "input": total_in,
            "output": total_out,
        },
    }

    print(json.dumps(summary, indent=2))

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    p_sum = sub.add_parser("summarize")
    p_sum.add_argument("judged_path")

    args = parser.parse_args()

    if args.command == "summarize":
        summarize(args.judged_path)