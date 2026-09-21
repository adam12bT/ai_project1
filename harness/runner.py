"""
Runs the explainer system on every item in a split of the golden set and
writes one row per item to results/. This is the harness's core contract:
one command, one result per item, every time.

Usage:
    python -m harness.runner --prompt prompts/explainer_v1.txt --split dev --run-name v1_dev
"""

from __future__ import annotations

import argparse
import time

import groq
from tqdm import tqdm

from harness import config
from harness.schema import EXPLAIN_TOOL, call_with_tool, read_jsonl, write_jsonl


def run(prompt_path: str, split: str, run_name: str) -> str:
    system_prompt = open(prompt_path, encoding="utf-8").read()
    golden_set = read_jsonl(config.GOLDEN_SET_PATH)
    items = [item for item in golden_set if item.get("split") == split]

    if not items:
        raise ValueError(
            f"No items with split='{split}' in {config.GOLDEN_SET_PATH}. "
            f"Check the 'split' field on your golden set rows."
        )

    client = groq.Groq()
    rows = []

    for item in tqdm(items, desc=f"Running {run_name}"):
        start = time.time()

        try:
            result = call_with_tool(
                client=client,
                model=config.EXPLAINER_MODEL,
                system=system_prompt,
                user_content=f"SQL query:\n```sql\n{item['query']}\n```",
                tool=EXPLAIN_TOOL,
                max_tokens=config.MAX_TOKENS_EXPLAINER,
            )

            rows.append(
                {
                    "id": item["id"],
                    "query": item["query"],
                    "gold_checklist": item.get("gold_checklist"),
                    "explanation": result.data["explanation"],
                    "clauses_covered": result.data.get("clauses_covered", []),
                    "model": config.EXPLAINER_MODEL,
                    "prompt_file": prompt_path,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "latency_s": round(time.time() - start, 3),
                    "error": None,
                }
            )

        except Exception as e:
            rows.append(
                {
                    "id": item["id"],
                    "query": item["query"],
                    "gold_checklist": item.get("gold_checklist"),
                    "explanation": None,
                    "clauses_covered": [],
                    "model": config.EXPLAINER_MODEL,
                    "prompt_file": prompt_path,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "latency_s": round(time.time() - start, 3),
                    "error": str(e),
                }
            )

    out_path = config.RESULTS_DIR / f"run_{run_name}.jsonl"
    write_jsonl(out_path, rows)

    n_errors = sum(1 for r in rows if r["error"])
    print(f"Wrote {len(rows)} rows ({n_errors} errors) to {out_path}")

    return str(out_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prompt",
        required=True,
        help="Path to the explainer system prompt",
    )
    parser.add_argument(
        "--split",
        default="dev",
        choices=["dev", "test"],
    )
    parser.add_argument(
        "--run-name",
        required=True,
        help="Used to name the output file",
    )

    args = parser.parse_args()

    run(args.prompt, args.split, args.run_name)