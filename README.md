# Project 1 — The Grader
**Task:** Explaining a SQL query in plain words
**Team:** _(add names + roles here)_

## What this is

An evaluation harness for a system that takes a SQL query and produces a
plain-English explanation of what it does. The harness runs the system on a
golden set, scores every output with an LLM judge, and reports agreement
between the judge and humans, plus two bias checks (position, verbosity).

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GROQ_API_KEY=gsk_...
```

## Run

```bash
# 1. Run the explainer system on the golden set -> results/run_<name>.jsonl
python -m harness.runner --prompt prompts/explainer_v1.txt --split dev --run-name v1_dev

# 2. Judge the results -> results/judged_<name>.jsonl
python -m harness.judge score --results results/run_v1_dev.jsonl --out results/judged_v1_dev.jsonl

# 3. Reliability report: judge-vs-human agreement + position/verbosity bias
python -m harness.judge report --calibration data/calibration_set.jsonl --out results/reliability_report.json

# 4. Summarize a scored run (accuracy, cost, latency)
python -m harness.report summarize results/judged_v1_dev.jsonl
```

Every command works from a clean clone with just the two exports above.

## Repo layout

```
data/
  golden_set.jsonl        # 150+ items: query + gold checklist (dev/test split)
  calibration_set.jsonl   # (query, explanation, human_verdict) for judge calibration
  labelling_guide.md      # what "good" means, with examples
harness/
  schema.py               # structured-output schemas (explanation, verdict)
  runner.py                # runs the explainer system over a split
  judge.py                 # LLM judge: scoring + reliability report + bias checks
  report.py                 # summarize a scored run into numbers
prompts/
  explainer_v1.txt         # the system under test
  judge_v1.txt              # the grading rubric prompt
  CHANGELOG.md               # prompt version -> score, dated
results/
  *.jsonl                    # one row per item per run (git-ignored by default, keep a few for the demo)
```

## Cost model

`harness/report.py summarize` prints total input/output tokens and cost for
the run, using the per-model prices in `harness/pricing.py`. Update prices
there if they change — do not hardcode prices elsewhere.

## Contributions

| Member | Contribution |
|---|---|
| _name_ | _..._ |

## Notes

- No API keys are committed. `.env` is git-ignored; `GROQ_API_KEY` is read
  from the environment only.
- Model IDs are centralized in `harness/config.py` so a model swap is a
  one-line change, not a find-and-replace.
