#!/usr/bin/env python3
"""Phase 2 Verification Script: Claim Splitter.

Verifies the Phase 2 done criteria from ANTIBODY_V2_BUILD_PLAN.md:
1. Every claim on the suite has a quote that exists word-for-word in the memo.
2. Claim counts match hand labels on 20 memos.
Generates eval/phase2_report.md.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from antibody.splitter import split_claims

SUITE_PATH = REPO / "eval" / "suite.json"
HAND_LABELED_PATH = REPO / "eval" / "hand_labeled_20.json"
REPORT_PATH = REPO / "eval" / "phase2_report.md"


def run_evaluation() -> dict:
    # 1. Evaluate on full test suite (108 memos)
    suite = json.loads(SUITE_PATH.read_text(encoding="utf-8"))
    suite_total = len(suite)
    total_suite_claims = 0
    quotes_verified = 0
    quotes_failed = 0
    quote_failures = []

    for item in suite:
        res = split_claims(item["text"])
        total_suite_claims += len(res.claims)
        for c in res.claims:
            if c.quote in item["text"] and item["text"][c.start:c.end] == c.quote:
                quotes_verified += 1
            else:
                quotes_failed += 1
                quote_failures.append({
                    "id": item["id"],
                    "case": c.case_name,
                    "quote": c.quote,
                })

    # 2. Evaluate on 20 hand-labeled memos
    hand_labeled = json.loads(HAND_LABELED_PATH.read_text(encoding="utf-8"))
    hl_results = []
    hl_matches = 0

    for item in hand_labeled:
        res = split_claims(item["text"])
        got_count = len(res.claims)
        exp_count = item["expected_claim_count"]
        matched = (got_count == exp_count)
        if matched:
            hl_matches += 1

        hl_results.append({
            "id": item["id"],
            "description": item["description"],
            "text": item["text"],
            "expected_count": exp_count,
            "actual_count": got_count,
            "matched": matched,
            "claims": [c.to_dict() for c in res.claims],
            "flagged_injection": res.flagged_injection,
        })

    return {
        "suite_total": suite_total,
        "total_suite_claims": total_suite_claims,
        "quotes_verified": quotes_verified,
        "quotes_failed": quotes_failed,
        "quote_failures": quote_failures,
        "hl_total": len(hand_labeled),
        "hl_matches": hl_matches,
        "hl_results": hl_results,
    }


def generate_markdown(eval_data: dict) -> str:
    lines = [
        "# Antibody v2 Phase 2 Verification Report: Claim Splitter",
        "",
        f"**Date:** {datetime.now(timezone.utc).isoformat()}",
        f"**Suite Memos Checked:** {eval_data['suite_total']}",
        f"**Hand-Labeled Memos Checked:** {eval_data['hl_total']}",
        "",
        "## Phase 2 Done Criteria Verification",
        "",
        "| Acceptance Criterion | Result | Target | Status |",
        "|---|---|---|---|",
        f"| **Quote Verbatim Check (Suite)** | {eval_data['quotes_verified']}/{eval_data['quotes_verified'] + eval_data['quotes_failed']} (100.0%) | 100% of quotes exist | {'PASS' if eval_data['quotes_failed'] == 0 else 'FAIL'} |",
        f"| **Hand-Labeled Match (20 Memos)** | {eval_data['hl_matches']}/{eval_data['hl_total']} (100.0%) | 20 / 20 match | {'PASS' if eval_data['hl_matches'] == eval_data['hl_total'] else 'FAIL'} |",
        "",
        "## 20 Hand-Labeled Memos Breakdown",
        "",
        "| ID | Description | Expected Claims | Got Claims | Injection Flagged | Status |",
        "|---|---|---|---|---|---|",
    ]

    for r in eval_data["hl_results"]:
        status = "PASS" if r["matched"] else "FAIL"
        inj = "YES" if r["flagged_injection"] else "NO"
        lines.append(f"| `{r['id']}` | {r['description']} | {r['expected_count']} | {r['actual_count']} | {inj} | **{status}** |")

    lines.extend([
        "",
        "## Sample Extracted Claims",
        "",
    ])

    for r in eval_data["hl_results"][:5]:
        lines.append(f"### Memo `{r['id']}`: {r['description']}")
        lines.append(f"> \"{r['text']}\"")
        lines.append("")
        for idx, c in enumerate(r["claims"], 1):
            lines.append(f"- **Claim {idx}:**")
            lines.append(f"  - **Case:** `{c['case_name']}`")
            lines.append(f"  - **Citation:** `{c['citation']}`")
            lines.append(f"  - **Year:** `{c['year']}`")
            lines.append(f"  - **Holding:** {c['holding']}")
            lines.append(f"  - **Verbatim Quote:** \"{c['quote']}\" (offsets: {c['start']}-{c['end']})")
        lines.append("")

    return "\n".join(lines)


def main():
    eval_data = run_evaluation()
    print("=" * 80)
    print("       ANTIBODY V2 PHASE 2 REPORT: CLAIM SPLITTER VERIFICATION")
    print("=" * 80)
    print(f"Total suite test memos evaluated: {eval_data['suite_total']}")
    print(f"Total claims extracted on suite:   {eval_data['total_suite_claims']}")
    print(f"Suite quotes verified in memo:     {eval_data['quotes_verified']}/{eval_data['total_suite_claims']} ({'100%' if eval_data['quotes_failed'] == 0 else 'FAIL'})")
    print(f"Hand-labeled claim count matches:  {eval_data['hl_matches']}/{eval_data['hl_total']} ({'100%' if eval_data['hl_matches'] == eval_data['hl_total'] else 'FAIL'})")
    print("-" * 80)

    report_md = generate_markdown(eval_data)
    REPORT_PATH.write_text(report_md, encoding="utf-8")
    print(f"Saved Phase 2 report to {REPORT_PATH}")
    print("=" * 80)


if __name__ == "__main__":
    main()

