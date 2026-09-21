
"""
Turns a judged run (results/judged_*.jsonl) into the numbers the report
needs: pass rate, score distribution, cost, latency. Never collapses
everything into one summary number — counts and percentages, per the brief.

Usage:
    python -m harness.report summarize results/judged_v1_dev.jsonl
"""
