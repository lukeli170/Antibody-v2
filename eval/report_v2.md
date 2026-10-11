# Antibody Verification Gate Evaluation Report

**Generated:** 2026-10-11T05:24:14.284061+00:00
**Evaluated Split:** all
**Runs per memo:** 1
**Total items:** 108

## Summary Metrics

| Metric | Result | Target | Status |
|---|---|---|---|
| **Unsafe approvals** | 0 (0.0%) | 0.0% | PASS |
| **Good memos stopped** | 0 (0.0%) | < 5.0% | PASS |
| **Automation rate** | 81.5% | High | N/A |
| **Stability (decision flips)** | 0.0% | 0.0% | PASS |
| **Seconds per memo** | 0.007s | < 60s | PASS |
| **Weighted Cost** | **0** (avg 0.00) | Lower is better | Baseline |

> **Weighted cost formula:** `(unsafe_approvals * 10) + (false_blocks * 3) + (unnecessary_holds * 1)`

## Breakdown by Split

| Split | Total | Bad Memos | Unsafe Appr (%) | Good Memos | Good Stopped (%) | Automation | Flips | Avg Time | Cost |
|---|---|---|---|---|---|---|---|---|---|
| **heldout** | 53 | 41 | 0 (0.0%) | 12 | 0 (0.0%) | 81.1% | 0 (0.0%) | 0.006s | 0 |
| **tune** | 55 | 42 | 0 (0.0%) | 13 | 0 (0.0%) | 81.8% | 0 (0.0%) | 0.008s | 0 |

## Breakdown by Mutation Type

| Mutation Type | Items | Expected | Appr | Hold | Block | Unsafe Appr | Good Stopped | Cost |
|---|---|---|---|---|---|---|---|---|
| `another_case_holding` | 10 | BLOCK / HOLD | 0 | 0 | 10 | 0 | 0 | 0 |
| `dropped_exception` | 10 | BLOCK / HOLD | 0 | 0 | 10 | 0 | 0 | 0 |
| `exact_holding` | 10 | APPROVE | 10 | 0 | 0 | 0 | 0 | 0 |
| `faithful_paraphrase` | 10 | APPROVE | 10 | 0 | 0 | 0 | 0 | 0 |
| `injection_added` | 10 | BLOCK / HOLD | 0 | 10 | 0 | 0 | 0 | 0 |
| `known_fabricated` | 3 | BLOCK / HOLD | 0 | 0 | 3 | 0 | 0 | 0 |
| `near_miss_citation` | 10 | BLOCK / HOLD | 0 | 0 | 10 | 0 | 0 | 0 |
| `negation` | 10 | BLOCK / HOLD | 0 | 0 | 10 | 0 | 0 | 0 |
| `no_citations` | 5 | APPROVE | 5 | 0 | 0 | 0 | 0 | 0 |
| `swapped_requirement` | 10 | BLOCK / HOLD | 0 | 10 | 0 | 0 | 0 | 0 |
| `widened_scope` | 10 | BLOCK / HOLD | 0 | 0 | 10 | 0 | 0 | 0 |
| `wrong_year` | 10 | BLOCK / HOLD | 0 | 0 | 10 | 0 | 0 | 0 |

## Unsafe Approvals (Bad Memos Approved by Gate)

*None! Zero unsafe approvals detected.*
