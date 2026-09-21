"""
Runs the explainer system on every item in a split of the golden set and
writes one row per item to results/. This is the harness's core contract:
one command, one result per item, every time.

Usage:
    python -m harness.runner --prompt prompts/explainer_v1.txt --split dev --run-name v1_dev
"""
