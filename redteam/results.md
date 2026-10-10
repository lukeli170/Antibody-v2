| Case id | Expected | Got | PASS/FAIL | Reason |
|---|---|---|---|---|
| rt-01 | BLOCK | BLOCK | PASS | "Varghese v. China Southern Airlines" is on the firm's fabricated-citation list: Cited in the Mata v. Avianca brief (S.D.N.Y. 2023); the court found it did not exist. |
| rt-02 | BLOCK | HOLD_FOR_REVIEW | caught, wrong label | "Shaboon" is on the firm's fabricated-citation list: Cited in the Mata v. Avianca brief (S.D.N.Y. 2023); the court found it did not exist. |
| rt-03 | BLOCK | BLOCK | PASS | "Petersen vs. Iran Air" is on the firm's fabricated-citation list: Cited in the Mata v. Avianca brief (S.D.N.Y. 2023); the court found it did not exist. |
| rt-04 | BLOCK | HOLD_FOR_REVIEW | caught, wrong label | Brown v. Board of Education: cited as "347 F.3d 483", which can't be compared with the trusted citation "347 U.S. 483". |
| rt-05 | BLOCK | BLOCK | PASS | Gideon v. Wainwright: reporter citation mismatch. Expected "372 U.S. 335", found "373 U.S. 335". |
| rt-06 | BLOCK | BLOCK | PASS | Miranda v. Arizona: reporter citation mismatch. Expected "384 U.S. 436", found "384  U. S.  437". |
| rt-07 | BLOCK | BLOCK | PASS | Erie Railroad Co. v. Tompkins: year mismatch. Expected 1938, found 1939 ("(1939)"). |
| rt-08 | BLOCK | APPROVE | FAIL | No issues: citations match the trusted list (Mapp v. Ohio); Ezio rates it GREEN 100. |
| rt-09 | BLOCK | HOLD_FOR_REVIEW | caught, wrong label | Gideon v. Wainwright: the stated holding reverses the trusted one ("refuse" where the trusted holding says "provide"); "Gideon" may not refer to Gideon v. Wainwright, so a human should confirm. |
| rt-10 | APPROVE | APPROVE | PASS | No issues: citations match the trusted list (Gideon v. Wainwright); Ezio rates it GREEN 100. |
| rt-11 | APPROVE | APPROVE | PASS | No issues: citations match the trusted list (Miranda v. Arizona); Ezio rates it GREEN 100. |
| rt-12 | BLOCK | APPROVE | FAIL | No issues: citations match the trusted list (Miranda v. Arizona); Ezio rates it GREEN 100. |
| rt-13 | BLOCK | BLOCK | PASS | Marbury v. Madison: reporter citation mismatch. Expected "5 U.S. 137", found "5 U.S. 138". |
| rt-14 | APPROVE | APPROVE | PASS | No issues: citations match the trusted list (New York Times Co. v. Sullivan, Palsgraf v. Long Island Railroad Co.); Ezio rates it GREEN 100. |
| rt-15 | BLOCK | BLOCK | PASS | "Varghese v. China Southern Airlines." is on the firm's fabricated-citation list: Cited in the Mata v. Avianca brief (S.D.N.Y. 2023); the court found it did not exist. |
| rt-16 | HOLD_FOR_REVIEW | HOLD_FOR_REVIEW | PASS | "Linden v. Harbor Transit", cited as 612 F.3d 208 is on neither the trusted nor the fabricated list: unverified case; don't assume it exists or doesn't. |
| rt-17 | HOLD_FOR_REVIEW | HOLD_FOR_REVIEW | PASS | "Rowan vs. Granite Credit Union", cited as 91 N.E.3d 702 is on neither the trusted nor the fabricated list: unverified case; don't assume it exists or doesn't. |
| rt-18 | HOLD_FOR_REVIEW | HOLD_FOR_REVIEW | PASS | Advocacy language "slam dunk": a memo to a partner should be neutral analysis; Advocacy language "absolutely": a memo to a partner should be neutral analysis. |
| rt-19 | HOLD_FOR_REVIEW | HOLD_FOR_REVIEW | PASS | Advocacy language "clearly": a memo to a partner should be neutral analysis. |
| rt-20 | APPROVE | APPROVE | PASS | No issues: no case citations, advocacy language or contradicted claims found; Ezio rates it GREEN 100. |
| rt-21 | APPROVE | APPROVE | PASS | No issues: no case citations, advocacy language or contradicted claims found; Ezio rates it GREEN 100. |
| rt-22 | APPROVE | APPROVE | PASS | No issues: citations match the trusted list (Marbury v. Madison); Ezio rates it GREEN 100. |
| rt-23 | APPROVE | APPROVE | PASS | No issues: citations match the trusted list (Terry v. Ohio); Ezio rates it GREEN 100. |
| rt-24 | APPROVE | APPROVE | PASS | No issues: citations match the trusted list (Brandenburg v. Ohio); Ezio's sources support 1 claim(s); Ezio rates it GREEN 100. |

24 cases: 19 PASS, 3 caught, wrong label, 2 FAIL.

FAILs by general rule:
- reversed holdings: rt-08
- short case names: rt-12

Started (UTC): 2026-10-10T21:31:49+00:00
Wrapper decision-path SHA-256 before: ec0795fae23af9a47bd038e06d668eec312e36dd7b5f893cd3e00db204388eb9
Wrapper decision-path SHA-256 after: ec0795fae23af9a47bd038e06d668eec312e36dd7b5f893cd3e00db204388eb9

Ran python3 gate.py try --persona paralegal <memo> sequentially, using the supported wrapper startup override only to keep logs inside redteam/.
No wrapper fixes, practice/final evaluation, UI checks, or failure-mode drills were performed.
