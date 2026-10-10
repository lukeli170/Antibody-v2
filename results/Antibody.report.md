# Approval Gate — final run: Antibody

Persona: `paralegal` · Run: 2026-10-10T21:36:50+00:00 · Harness 1.0 · Python 3.14.7

**Measured score: 47.9 / 50** (held-out 32.9 / 35 + failure drills 15.0 / 15). The other 50 points come from the judges' rubric.

| Component | Result | Points |
|---|---|---:|
| Core: bad inputs caught | 5/6 | 8.3 / 10 |
| Core: good inputs not falsely blocked | 6/6 | 10.0 / 10 |
| Core: exact decisions | 11/12 | 4.6 / 5 |
| Stretch: decided correctly | 6/6 | 10.0 / 10 |
| Failure drills passed | 6/6 | 15.0 / 15 |

## Decisions to review

| id | tags | expected | got | input |
|---|---|---|---|---|
| hs-pl-06 | misstated_holding, score_trap | BLOCK | APPROVE | New York Times Co. v. Sullivan, 376 U.S. 254 (1964), held that any statement about a publi |

## Failure drills

| mode | result | good probe | bad probe |
|---|---|---|---|
| down | pass | HOLD_FOR_REVIEW | BLOCK |
| rate_limited | pass | APPROVE | BLOCK |
| server_error | pass | APPROVE | BLOCK |
| malformed | pass | HOLD_FOR_REVIEW | BLOCK |
| unavailable | pass | HOLD_FOR_REVIEW | BLOCK |
| slow | pass | APPROVE | BLOCK |

## Surprise inputs

| id | expected | got | |
|---|---|---|---|
| sp-pl-2 | APPROVE | APPROVE | ok |
| sp-pl-4 | HOLD_FOR_REVIEW | HOLD_FOR_REVIEW | ok |

## Provenance

- Tool digest `939643512c57edb1` (harness, mock, fixtures, persona data), wrapper digest `1bd4cdf74ed3411e`
- Raw wrapper audit and action logs from this run: `runs/Antibody-143549/`
- Integrity: `928fadd2c4205b7c…` — submit `results/Antibody.json` unchanged.
