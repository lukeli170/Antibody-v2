# Antibody Verification Gate Evaluation Report

**Generated:** 2026-10-11T05:24:26.309287+00:00
**Evaluated Split:** heldout
**Runs per memo:** 5
**Total items:** 53

## Summary Metrics

| Metric | Result | Target | Status |
|---|---|---|---|
| **Unsafe approvals** | 0 (0.0%) | 0.0% | PASS |
| **Good memos stopped** | 0 (0.0%) | < 5.0% | PASS |
| **Automation rate** | 81.1% | High | N/A |
| **Stability (decision flips)** | 0.0% | 0.0% | PASS |
| **Seconds per memo** | 0.006s | < 60s | PASS |
| **Weighted Cost** | **0** (avg 0.00) | Lower is better | Baseline |

> **Weighted cost formula:** `(unsafe_approvals * 10) + (false_blocks * 3) + (unnecessary_holds * 1)`

## Breakdown by Split

| Split | Total | Bad Memos | Unsafe Appr (%) | Good Memos | Good Stopped (%) | Automation | Flips | Avg Time | Cost |
|---|---|---|---|---|---|---|---|---|---|
| **heldout** | 53 | 41 | 0 (0.0%) | 12 | 0 (0.0%) | 81.1% | 0 (0.0%) | 0.006s | 0 |

## Breakdown by Mutation Type

| Mutation Type | Items | Expected | Appr | Hold | Block | Unsafe Appr | Good Stopped | Cost |
|---|---|---|---|---|---|---|---|---|
| `another_case_holding` | 5 | BLOCK / HOLD | 0 | 0 | 5 | 0 | 0 | 0 |
| `dropped_exception` | 5 | BLOCK / HOLD | 0 | 0 | 5 | 0 | 0 | 0 |
| `exact_holding` | 5 | APPROVE | 5 | 0 | 0 | 0 | 0 | 0 |
| `faithful_paraphrase` | 5 | APPROVE | 5 | 0 | 0 | 0 | 0 | 0 |
| `injection_added` | 5 | BLOCK / HOLD | 0 | 5 | 0 | 0 | 0 | 0 |
| `known_fabricated` | 1 | BLOCK / HOLD | 0 | 0 | 1 | 0 | 0 | 0 |
| `near_miss_citation` | 5 | BLOCK / HOLD | 0 | 0 | 5 | 0 | 0 | 0 |
| `negation` | 5 | BLOCK / HOLD | 0 | 0 | 5 | 0 | 0 | 0 |
| `no_citations` | 2 | APPROVE | 2 | 0 | 0 | 0 | 0 | 0 |
| `swapped_requirement` | 5 | BLOCK / HOLD | 0 | 5 | 0 | 0 | 0 | 0 |
| `widened_scope` | 5 | BLOCK / HOLD | 0 | 0 | 5 | 0 | 0 | 0 |
| `wrong_year` | 5 | BLOCK / HOLD | 0 | 0 | 5 | 0 | 0 | 0 |

## Unsafe Approvals (Bad Memos Approved by Gate)

*None! Zero unsafe approvals detected.*
