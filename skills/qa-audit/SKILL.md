---
name: qa-audit
description: Validate audit outputs for completeness, evidence quality, layer routing accuracy, and fix clarity before delivery.
---

# QA Audit

Run after any audit to validate the output before delivery.

## Checks

- Every finding has a location, evidence, visitor impact, root cause, and exact fix
- Evidence is real (no invented rankings, traffic, or AI citations)
- Route matches the problem type (conversion vs visibility vs combined)
- Layer classification is correct (business vs messaging vs offer vs trust vs conversion)
- Priority order makes sense (upstream before downstream)
- Recommendations are actionable, not generic
- Client-facing version removes internal notes

## Output

- PASS or FAIL per check
- List of warnings and errors
- Required fixes before delivery
