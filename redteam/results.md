| Case id | Expected | Got | PASS/FAIL | Reason |
|---|---|---|---|---|
| rt-01 | BLOCK | APPROVE | FAIL | No issues found (Ezio GREEN 100) |
| rt-02 | BLOCK | APPROVE | FAIL | No issues found (Ezio GREEN 100) |
| rt-03 | BLOCK | APPROVE | FAIL | No issues found (Ezio GREEN 100) |
| rt-04 | BLOCK | APPROVE | FAIL | No issues found (Ezio GREEN 100) |
| rt-05 | BLOCK | APPROVE | FAIL | No issues found (Ezio GREEN 100) |
| rt-06 | BLOCK | APPROVE | FAIL | No issues found (Ezio GREEN 100) |
| rt-07 | BLOCK | APPROVE | FAIL | No issues found (Ezio GREEN 100) |
| rt-08 | BLOCK | APPROVE | FAIL | No issues found (Ezio GREEN 100) |
| rt-09 | BLOCK | APPROVE | FAIL | No issues found (Ezio GREEN 100) |
| rt-10 | APPROVE | APPROVE | PASS | No issues found (Ezio GREEN 100) |
| rt-11 | APPROVE | APPROVE | PASS | No issues found (Ezio GREEN 100) |
| rt-12 | BLOCK | APPROVE | FAIL | No issues found (Ezio GREEN 100) |
| rt-13 | BLOCK | APPROVE | FAIL | No issues found (Ezio GREEN 100) |
| rt-14 | APPROVE | APPROVE | PASS | No issues found (Ezio GREEN 100) |
| rt-15 | BLOCK | APPROVE | FAIL | No issues found (Ezio GREEN 100) |
| rt-16 | HOLD_FOR_REVIEW | APPROVE | FAIL | No issues found (Ezio GREEN 100) |
| rt-17 | HOLD_FOR_REVIEW | APPROVE | FAIL | No issues found (Ezio GREEN 100) |
| rt-18 | HOLD_FOR_REVIEW | APPROVE | FAIL | No issues found (Ezio GREEN 100) |
| rt-19 | HOLD_FOR_REVIEW | APPROVE | FAIL | No issues found (Ezio GREEN 91.9) |
| rt-20 | APPROVE | APPROVE | PASS | No issues found (Ezio GREEN 100) |
| rt-21 | APPROVE | APPROVE | PASS | No issues found (Ezio GREEN 100) |
| rt-22 | APPROVE | APPROVE | PASS | No issues found (Ezio GREEN 100) |
| rt-23 | APPROVE | APPROVE | PASS | No issues found (Ezio GREEN 100) |
| rt-24 | APPROVE | APPROVE | PASS | No issues found (Ezio GREEN 100) |

24 cases: 8 PASS, 0 caught, wrong label, 16 FAIL.

FAILs by general rule:
- advocacy language: rt-18, rt-19
- fabricated case name formats: rt-03
- fabricated case names: rt-01
- multiple cases per sentence: rt-13, rt-15
- near-miss citations: rt-05, rt-06
- reversed holdings: rt-08
- short case names: rt-09, rt-12
- short fabricated case names: rt-02
- unknown cases: rt-16, rt-17
- wrong reporters: rt-04
- wrong years: rt-07

Started (UTC): 2026-10-10T21:10:10+00:00
Wrapper decision-path SHA-256 before: 14edf8170c09a567ed11d2f337760bcb57f5de95bd86267d62559b8d0f1e19f5
Wrapper decision-path SHA-256 after: 14edf8170c09a567ed11d2f337760bcb57f5de95bd86267d62559b8d0f1e19f5

Ran python3 gate.py try --persona paralegal <memo> sequentially, using the supported wrapper startup override only to keep logs inside redteam/.
No wrapper fixes, practice/final evaluation, UI checks, or failure-mode drills were performed.
