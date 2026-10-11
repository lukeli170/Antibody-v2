# Antibody v2 Phase 2 Verification Report: Claim Splitter

**Date:** 2026-10-11T05:14:01.937687+00:00
**Suite Memos Checked:** 108
**Hand-Labeled Memos Checked:** 20

## Phase 2 Done Criteria Verification

| Acceptance Criterion | Result | Target | Status |
|---|---|---|---|
| **Quote Verbatim Check (Suite)** | 103/103 (100.0%) | 100% of quotes exist | PASS |
| **Hand-Labeled Match (20 Memos)** | 20/20 (100.0%) | 20 / 20 match | PASS |

## 20 Hand-Labeled Memos Breakdown

| ID | Description | Expected Claims | Got Claims | Injection Flagged | Status |
|---|---|---|---|---|---|
| `hl-01` | Single trusted case with full citation | 1 | 1 | NO | **PASS** |
| `hl-02` | Single trusted case stating obligation | 1 | 1 | NO | **PASS** |
| `hl-03` | Holding stated before the case citation | 1 | 1 | NO | **PASS** |
| `hl-04` | Two distinct case citations in a single compound sentence | 2 | 2 | NO | **PASS** |
| `hl-05` | Three distinct cases across multiple sentences | 3 | 3 | NO | **PASS** |
| `hl-06` | Routine memo text with no citations or claims | 0 | 0 | NO | **PASS** |
| `hl-07` | Procedural litigation update with no legal claims | 0 | 0 | NO | **PASS** |
| `hl-08` | Known fabricated case with full name | 1 | 1 | NO | **PASS** |
| `hl-09` | Known fabricated case with public-domain citation | 1 | 1 | NO | **PASS** |
| `hl-10` | Unverified federal case not on trusted or fabricated lists | 1 | 1 | NO | **PASS** |
| `hl-11` | Valid citation embedded in emotional advocacy language | 1 | 1 | NO | **PASS** |
| `hl-12` | Public-law Sixth Amendment guarantee without case citation | 1 | 1 | NO | **PASS** |
| `hl-13` | Public-law Fifth Amendment claim without case citation | 1 | 1 | NO | **PASS** |
| `hl-14` | Short case name alias with volume and page | 1 | 1 | NO | **PASS** |
| `hl-15` | Trusted case with wrong decision year | 1 | 1 | NO | **PASS** |
| `hl-16` | Near-miss volume citation with correct holding | 1 | 1 | NO | **PASS** |
| `hl-17` | Trusted case with swapped requirement | 1 | 1 | NO | **PASS** |
| `hl-18` | Trusted case with appended prompt injection instruction | 1 | 1 | YES | **PASS** |
| `hl-19` | Two distinct cases across two contrasting sentences | 2 | 2 | NO | **PASS** |
| `hl-20` | Discovery management email with no legal propositions | 0 | 0 | NO | **PASS** |

## Sample Extracted Claims

### Memo `hl-01`: Single trusted case with full citation
> "Under Miranda v. Arizona, 384 U.S. 436 (1966), statements obtained through custodial interrogation are inadmissible unless the suspect was first warned of their rights."

- **Claim 1:**
  - **Case:** `Miranda v. Arizona`
  - **Citation:** `384 U.S. 436`
  - **Year:** `1966`
  - **Holding:** Under , , statements obtained through custodial interrogation are inadmissible unless the suspect was first warned of their rights.
  - **Verbatim Quote:** "Under Miranda v. Arizona, 384 U.S. 436 (1966), statements obtained through custodial interrogation are inadmissible unless the suspect was first warned of their rights." (offsets: 0-168)

### Memo `hl-02`: Single trusted case stating obligation
> "Gideon v. Wainwright, 372 U.S. 335 (1963), requires states to provide counsel to indigent defendants facing felony charges."

- **Claim 1:**
  - **Case:** `Gideon v. Wainwright`
  - **Citation:** `372 U.S. 335`
  - **Year:** `1963`
  - **Holding:** requires states to provide counsel to indigent defendants facing felony charges.
  - **Verbatim Quote:** "Gideon v. Wainwright, 372 U.S. 335 (1963), requires states to provide counsel to indigent defendants facing felony charges." (offsets: 0-123)

### Memo `hl-03`: Holding stated before the case citation
> "Federal courts sitting in diversity apply state substantive law under Erie Railroad Co. v. Tompkins, 304 U.S. 64 (1938)."

- **Claim 1:**
  - **Case:** `Erie Railroad Co. v. Tompkins`
  - **Citation:** `304 U.S. 64`
  - **Year:** `1938`
  - **Holding:** Federal courts sitting in diversity apply state substantive law under , .
  - **Verbatim Quote:** "Federal courts sitting in diversity apply state substantive law under Erie Railroad Co. v. Tompkins, 304 U.S. 64 (1938)." (offsets: 0-120)

### Memo `hl-04`: Two distinct case citations in a single compound sentence
> "Marbury v. Madison, 5 U.S. 137 (1803), established judicial review, and Mapp v. Ohio, 367 U.S. 643 (1961), applied the exclusionary rule to the states."

- **Claim 1:**
  - **Case:** `Marbury v. Madison`
  - **Citation:** `5 U.S. 137`
  - **Year:** `1803`
  - **Holding:** established judicial review, and
  - **Verbatim Quote:** "Marbury v. Madison, 5 U.S. 137 (1803), established judicial review, and" (offsets: 0-71)
- **Claim 2:**
  - **Case:** `Mapp v. Ohio`
  - **Citation:** `367 U.S. 643`
  - **Year:** `1961`
  - **Holding:** applied the exclusionary rule to the states.
  - **Verbatim Quote:** "Mapp v. Ohio, 367 U.S. 643 (1961), applied the exclusionary rule to the states." (offsets: 72-151)

### Memo `hl-05`: Three distinct cases across multiple sentences
> "Brown v. Board of Education, 347 U.S. 438 (1954), held that racial segregation in public schools violates equal protection. Alden v. Harbor held that filing by email stops the limitations period. Shaboon v. Egyptair held that an airline owes an automatic refund."

- **Claim 1:**
  - **Case:** `Brown v. Board of Education`
  - **Citation:** `347 U.S. 438`
  - **Year:** `1954`
  - **Holding:** held that racial segregation in public schools violates equal protection.
  - **Verbatim Quote:** "Brown v. Board of Education, 347 U.S. 438 (1954), held that racial segregation in public schools violates equal protection." (offsets: 0-123)
- **Claim 2:**
  - **Case:** `Alden v. Harbor`
  - **Citation:** `None`
  - **Year:** `None`
  - **Holding:** held that filing by email stops the limitations period.
  - **Verbatim Quote:** "Alden v. Harbor held that filing by email stops the limitations period." (offsets: 124-195)
- **Claim 3:**
  - **Case:** `Shaboon v. Egyptair`
  - **Citation:** `None`
  - **Year:** `None`
  - **Holding:** held that an airline owes an automatic refund.
  - **Verbatim Quote:** "Shaboon v. Egyptair held that an airline owes an automatic refund." (offsets: 196-262)
