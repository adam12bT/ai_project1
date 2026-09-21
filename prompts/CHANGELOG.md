# Prompt changelog

Every entry links a prompt change to a before/after score on the **dev**
split (never test — test is reported once, at the end). Run:

```bash
python -m harness.runner --prompt prompts/explainer_v1.txt --split dev --run-name v1_dev
python -m harness.judge score --results results/run_v1_dev.jsonl --out results/judged_v1_dev.jsonl
python -m harness.report summarize results/judged_v1_dev.jsonl
```

before and after each change, and paste the pass_rate_pct here.

| Date | Prompt file | Change | Dev pass rate before | Dev pass rate after | Notes |
|---|---|---|---|---|---|
| _YYYY-MM-DD_ | explainer_v1.txt | Initial version | — | _TBD_ | Baseline. Explicit rule about INNER vs LEFT JOIN added after noticing this was the most common gold-checklist miss in a first manual pass over 10 items. |

Judge prompt changes get their own row and must be re-validated against
`data/calibration_set.jsonl` (rerun `harness.judge report`) — a judge prompt
change can silently break the reliability numbers even if it looks like a
small wording tweak.

| Date | Prompt file | Change | Judge-human agreement before | after | Notes |
|---|---|---|---|---|---|
| _YYYY-MM-DD_ | judge_v1.txt | Initial version | — | _TBD_ | |
