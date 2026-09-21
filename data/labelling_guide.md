# Labelling guide — SQL query explanations

**Task:** given a SQL query, is a plain-English explanation of it good or bad?

## What "good" means

An explanation gets a **pass** only if all four hold. One miss on any of
them is a **fail** — there is no partial credit at the label stage (the
judge's 1-5 score exists for finer-grained tracking, but the pass/fail label
you assign by hand should be binary and strict).

1. **Correct** — every clause is described accurately. Getting a JOIN type
   backwards, an aggregation grouping wrong, or a filter direction flipped
   (`>` vs `<`) is an automatic fail.
2. **Complete** — nothing in the query is silently dropped. If the query has
   a HAVING clause on top of a WHERE clause, the explanation must reflect
   both as separate filters, not merge them into one.
3. **No hallucination** — doesn't claim the query does something it
   doesn't. This includes over-interpreting business intent that isn't
   actually enforced by the query (see example 3 below).
4. **Clear** — a reader with no SQL background could act on this
   explanation without seeing the query.

## Worked examples

**Example 1 — JOIN direction (the most common failure mode)**

```sql
SELECT c.name, o.order_id FROM customers c LEFT JOIN orders o ON c.id = o.customer_id;
```
- **Pass:** "Every customer is listed, along with their order ID if they
  have one — customers who've never ordered still appear, with a blank
  order ID."
- **Fail:** "This shows customer names and order IDs for customers who have
  ordered." — this describes INNER JOIN behavior, not LEFT JOIN. The
  explanation drops the "customers with zero orders are still included"
  fact, which is the entire point of using LEFT JOIN over INNER JOIN.

**Example 2 — merging separate filters**

```sql
SELECT customer_id, SUM(amount) FROM orders WHERE order_date >= '2025-01-01' GROUP BY customer_id HAVING SUM(amount) > 1000;
```
- **Pass:** explanation mentions the date filter (orders since Jan 1 2025)
  AND the spending threshold (total over 1000) as two distinct conditions.
- **Fail:** "Shows big spenders in 2025" — technically points at the right
  idea but is too vague to verify against the query; a labeller can't check
  whether "big" means >1000 without already knowing the query.

**Example 3 — hallucinated business intent**

```sql
SELECT name FROM employees e WHERE NOT EXISTS (SELECT 1 FROM projects p WHERE p.lead_id = e.id);
```
- **Pass:** "Employees who are not the lead of any project." (They could
  still be a team member on other projects — the query says nothing about
  that.)
- **Fail:** "Employees who currently have no project work." — invents a
  claim ("no project work") the query doesn't support; it only checks
  leadership, not membership.

## Process

- Two people label every item independently, then compare. Disagreements
  get discussed and resolved together; log the resolution here as a new
  example if it reveals an ambiguity in this guide.
- Report **inter-labeller agreement** (percent + Cohen's kappa) in the
  report. A low number here is a finding, not a failure — it tells you the
  rubric needs sharpening.
- Items where the two labellers can't agree even after discussion should be
  **dropped from the golden set**, with a count of how many were dropped
  and why (see `report.pdf` section 2).

## Scaling the calibration set

`data/calibration_set.jsonl` currently has 4 pass/fail pairs (8 rows) as a
format example. Before the demo, grow this to 30-40+ pairs — same query,
one human-labelled pass explanation and one human-labelled fail explanation
per pair — since this file powers both the judge-human agreement number and
the position-bias check.
