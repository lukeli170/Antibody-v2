# Paralegal evidence contract for the wrapper and UI

This is a proposed additive `/decide` response contract, not an implementation or a claim about current output. Keep the existing `decision`, `reason`, `evidence`, `ezio`, `signals`, and `action_executed` fields and their meanings. The current wrapper's findings and verified notes are useful inputs; the UI should receive structured evidence rather than parse those prose strings.

The backend owns every verdict and the final decision. The UI renders that evidence and offers draft edits; it must not turn a color, a score, or a clicked correction into approval.

## Required new response fields

| Field | Type | Meaning |
|---|---|---|
| `case_checks` | Array of objects below | One entry per case occurrence, including short names, repeated mentions, and multiple cases in one sentence. Empty when no case is mentioned or cited. |
| `review_question` | String or `null` | A concrete question/action when the final decision is `HOLD_FOR_REVIEW`; otherwise `null`. |
| `ezio_vs_ours` | Object below | Separate Ezio signals from the independent source-of-truth result. |
| `degraded` | Boolean | `true` when Ezio failed, timed out, exhausted retries/rate limits, returned malformed data, or reported accuracy `unavailable`. |
| `degraded_reason` | String or `null` | Nonempty explanation when degraded; otherwise `null`. |

Each `case_checks` entry has these required fields:

| Field | Type | Meaning |
|---|---|---|
| `case_name` | String | Canonical list name if matched, even for a short name; otherwise the name actually written. |
| `verdict` | Enum | `verified`, `unknown`, `fabricated`, or `wrong_detail`. |
| `memo_text` | String | Exact original passage attributed to this occurrence, including the stated detail being checked. |
| `start`, `end` | Integers | Passage offsets in the submitted memo: zero-based UTF-16 code units, end exclusive. `text.slice(start, end) === memo_text` in JavaScript. Do not count Python code points when non-BMP characters occur. |
| `source` | String or `null` | `trusted_citations.json`, `known_fabricated.json`, or `null` when neither list matches. |
| `checks` | Array | Objects with `field`, `status`, `memo_value`, and `trusted_value` as defined below. |
| `correction` | Object or `null` | An exact citation replacement only when a trusted citation mismatch is confirmed. |

Each `checks` object uses `field: "citation" | "year" | "holding"`, `status: "verified" | "wrong_detail" | "unknown"`, and string-or-null `memo_value` and `trusted_value`. Years are strings. `memo_value` quotes the stated value; `trusted_value` is the actual value from the matched trusted entry. Return checks only for stated details; absence is not verification. For unknown/fabricated cases, every `trusted_value` is `null`; do not invent a replacement or infer existence from absence on a list. A bare case mention can have `checks: []`.

`verified` means the case identity matched and every stated detail was actually checked. Report no unstated holding as verified. A confirmed reporter/year mismatch or reversed holding is `wrong_detail`; a holding or attribution the checker cannot resolve is `unknown` and needs a human. For an uncertain holding of a trusted case, retain `source: "trusted_citations.json"` and its actual `trusted_value`, with check `status: "unknown"`. Equivalent citation typography may verify after normalization, while `memo_value` preserves the submitted form.

A non-null `correction` contains `field: "citation"`, `start`, `end`, `memo_value`, and `trusted_value`. These offsets cover only the erroneous citation, using the same UTF-16 convention; `text.slice(start, end)` must equal `memo_value`. Apply it to that exact occurrence only, after checking the draft still matches. Then submit the revised draft for a fresh backend decision. The edit itself must neither approve nor execute the action; other case errors and tone issues may remain.

## Decision, queue, comparison, and fever display

Case severity is `fabricated`/`wrong_detail` → `BLOCK`, `unknown` → `HOLD_FOR_REVIEW`, `verified` → `APPROVE`. The final backend decision takes the most restrictive applicable result across cases, advocacy, Ezio contradictions, and service-failure policy. A green score never erases a known fabrication or trusted-list mismatch. No citations alone are not a reason to hold.

For HOLD, `review_question` must name the unresolved work: for example, “Confirm Alden v. Harbor exists and supports the stated filing-deadline rule.” For uncertain holdings, name the case and ask the reviewer to compare the attributed holding with the trusted entry. For advocacy, quote the phrase and request neutral analysis. For an Ezio outage, ask the reviewer to verify the unchecked claims or retry Ezio. Combine the outstanding questions when there are several. A session queue can store held responses and their submitted text; this contract does not add approval overrides or queue endpoints.

`ezio_vs_ours` contains exactly two objects:

- `ezio`: `tier` (`GREEN`/`YELLOW`/`RED` or `null`), `score` (finite number 0–100 or `null`), `accuracy_status` (`scored`/`not_scored`/`unavailable` or `null`), and `summary` (string).
- `ours`: `decision` (the independent list/tone result before Ezio policy) and `summary` (a concise, evidence-based explanation).

Show these side by side, with the existing top-level `decision` as the final gate. A `not_scored` accuracy status says “Accuracy not checked”; it is not an outage or factual verification. On failure, unavailable values are `null`, never a fabricated zero or GREEN score. If accuracy alone is unavailable, preserve the valid tier/score but show the limitation.

Render `verified` as “Verified (self)”, `unknown` as “Unknown (foreign, held)”, and `fabricated` as “Fabricated (known threat, blocked)”. Render `wrong_detail` separately as “Wrong detail (blocked)” with the trusted value. Use readable labels as well as colors. When `degraded` is true, show “Fever mode: Ezio could not complete verification; unresolved claims require review.” A preexisting independent BLOCK stays BLOCK, and its action stays unexecuted.

## Example response

Illustrative new memo (all characters are ASCII, so its UTF-16 offsets equal Python indices):

> Brown v. Board of Education, 347 U.S. 438 (1954), held that racial segregation in public schools violates equal protection. Alden v. Harbor held that filing by email stops the limitations period. Shaboon v. Egyptair held that an airline owes an automatic refund.

The `ezio` object below abbreviates the existing raw-response payload; preserve the full raw response in production. Proposed evidence fields are complete.

```json
{
  "decision": "BLOCK",
  "reason": "Brown has a wrong reporter page; Shaboon is on the fabricated list.",
  "evidence": [
    "Brown v. Board of Education: found 347 U.S. 438; trusted citation is 347 U.S. 483.",
    "Alden v. Harbor is on neither list; existence and holding need review.",
    "Shaboon v. Egyptair is on known_fabricated.json."
  ],
  "ezio": {"verdict": {"tier": "GREEN", "score": 86, "summary": "The memo looks fine."}},
  "action_executed": false,
  "case_checks": [
    {
      "case_name": "Brown v. Board of Education",
      "verdict": "wrong_detail",
      "memo_text": "Brown v. Board of Education, 347 U.S. 438 (1954), held that racial segregation in public schools violates equal protection.",
      "start": 0,
      "end": 123,
      "source": "trusted_citations.json",
      "checks": [
        {"field": "citation", "status": "wrong_detail", "memo_value": "347 U.S. 438", "trusted_value": "347 U.S. 483"},
        {"field": "year", "status": "verified", "memo_value": "1954", "trusted_value": "1954"},
        {"field": "holding", "status": "verified", "memo_value": "racial segregation in public schools violates equal protection", "trusted_value": "Racial segregation in public schools violates the Equal Protection Clause."}
      ],
      "correction": {"field": "citation", "start": 29, "end": 41, "memo_value": "347 U.S. 438", "trusted_value": "347 U.S. 483"}
    },
    {
      "case_name": "Alden v. Harbor",
      "verdict": "unknown",
      "memo_text": "Alden v. Harbor held that filing by email stops the limitations period.",
      "start": 124,
      "end": 195,
      "source": null,
      "checks": [
        {"field": "holding", "status": "unknown", "memo_value": "filing by email stops the limitations period", "trusted_value": null}
      ],
      "correction": null
    },
    {
      "case_name": "Shaboon v. Egyptair",
      "verdict": "fabricated",
      "memo_text": "Shaboon v. Egyptair held that an airline owes an automatic refund.",
      "start": 196,
      "end": 262,
      "source": "known_fabricated.json",
      "checks": [
        {"field": "holding", "status": "unknown", "memo_value": "an airline owes an automatic refund", "trusted_value": null}
      ],
      "correction": null
    }
  ],
  "review_question": null,
  "ezio_vs_ours": {
    "ezio": {"tier": "GREEN", "score": 86, "accuracy_status": "not_scored", "summary": "The memo looks fine; accuracy was not checked."},
    "ours": {"decision": "BLOCK", "summary": "A fabricated case and a wrong trusted citation require blocking; one other case is unknown."}
  },
  "degraded": false,
  "degraded_reason": null
}
```

`review_question` is null because this combined memo is BLOCK. A memo containing only the unknown occurrence would be HOLD and carry its specific existence-and-holding question.
