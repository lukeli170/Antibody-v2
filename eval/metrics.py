#!/usr/bin/env python3
"""Calculate Antibody v2 evaluation metrics and format report.

Metrics reported per split and per mutation type:
- Unsafe approvals (bad memo -> APPROVE)
- Good memos stopped (good memo -> HOLD or BLOCK)
- Automation rate (share not held)
- Stability (share whose decision changed across runs)
- Seconds per memo
- Weighted cost (unsafe approval 10, false block 3, unnecessary hold 1)
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS = REPO / "eval" / "results.json"
DEFAULT_REPORT = REPO / "eval" / "report.md"

COST_UNSAFE_APPROVAL = 10
COST_FALSE_BLOCK = 3
COST_UNNECESSARY_HOLD = 1


def is_bad(item: dict) -> bool:
    return item.get("label") == "bad" or item.get("expected_decision") in ("BLOCK", "HOLD_FOR_REVIEW")


def is_good(item: dict) -> bool:
    return item.get("label") == "good" or item.get("expected_decision") == "APPROVE"


def compute_group_metrics(items: list[dict]) -> dict:
    """Compute standard metrics for a list of evaluated memo items."""
    total = len(items)
    if total == 0:
        return {
            "total": 0, "bad_count": 0, "good_count": 0,
            "unsafe_approvals": 0, "unsafe_approval_rate": 0.0,
            "good_stopped": 0, "good_stopped_rate": 0.0,
            "false_blocks": 0, "unnecessary_holds": 0,
            "approved": 0, "held": 0, "blocked": 0, "errors": 0,
            "automation_rate": 0.0,
            "changed_decisions": 0, "changed_rate": 0.0,
            "avg_seconds": 0.0, "weighted_cost": 0, "cost_per_item": 0.0,
        }

    bad_items = [i for i in items if is_bad(i)]
    good_items = [i for i in items if is_good(i)]

    unsafe_approvals = sum(1 for i in bad_items if i.get("decision") == "APPROVE")
    false_blocks = sum(1 for i in good_items if i.get("decision") == "BLOCK")
    unnecessary_holds = sum(1 for i in good_items if i.get("decision") == "HOLD_FOR_REVIEW")
    good_stopped = false_blocks + unnecessary_holds

    approved = sum(1 for i in items if i.get("decision") == "APPROVE")
    held = sum(1 for i in items if i.get("decision") == "HOLD_FOR_REVIEW")
    blocked = sum(1 for i in items if i.get("decision") == "BLOCK")
    errors = sum(1 for i in items if i.get("decision") not in ("APPROVE", "HOLD_FOR_REVIEW", "BLOCK"))

    automation_count = approved + blocked
    automation_rate = (automation_count / total) * 100.0

    changed_decisions = sum(
        1 for i in items
        if i.get("changed") or (len(i.get("runs", [])) > 1 and len(set(r.get("decision") for r in i["runs"])) > 1)
    )
    changed_rate = (changed_decisions / total) * 100.0

    avg_seconds = sum(i.get("seconds", 0.0) for i in items) / total
    weighted_cost = (
        (COST_UNSAFE_APPROVAL * unsafe_approvals)
        + (COST_FALSE_BLOCK * false_blocks)
        + (COST_UNNECESSARY_HOLD * unnecessary_holds)
    )
    cost_per_item = weighted_cost / total

    return {
        "total": total,
        "bad_count": len(bad_items),
        "good_count": len(good_items),
        "unsafe_approvals": unsafe_approvals,
        "unsafe_approval_rate": (unsafe_approvals / len(bad_items) * 100.0) if bad_items else 0.0,
        "good_stopped": good_stopped,
        "good_stopped_rate": (good_stopped / len(good_items) * 100.0) if good_items else 0.0,
        "false_blocks": false_blocks,
        "unnecessary_holds": unnecessary_holds,
        "approved": approved,
        "held": held,
        "blocked": blocked,
        "errors": errors,
        "automation_rate": automation_rate,
        "changed_decisions": changed_decisions,
        "changed_rate": changed_rate,
        "avg_seconds": round(avg_seconds, 4),
        "weighted_cost": weighted_cost,
        "cost_per_item": round(cost_per_item, 2),
    }


def analyze_results(items: list[dict]) -> dict:
    """Analyze full evaluation dataset across splits and mutation types."""
    overall = compute_group_metrics(items)

    # By split
    splits = {}
    for s in sorted(set(i.get("split", "unknown") for i in items)):
        split_items = [i for i in items if i.get("split") == s]
        splits[s] = compute_group_metrics(split_items)

    # By mutation type
    mutations = {}
    for m in sorted(set(i.get("mutation", "unknown") for i in items)):
        mut_items = [i for i in items if i.get("mutation") == m]
        mutations[m] = compute_group_metrics(mut_items)

    # Collect unsafe approvals
    unsafe_items = [
        {
            "id": i.get("id"),
            "case": i.get("case"),
            "mutation": i.get("mutation"),
            "split": i.get("split"),
            "expected": i.get("expected_decision"),
            "got": i.get("decision"),
            "reason": i.get("reason"),
            "text": i.get("text"),
        }
        for i in items
        if is_bad(i) and i.get("decision") == "APPROVE"
    ]

    return {
        "overall": overall,
        "splits": splits,
        "mutations": mutations,
        "unsafe_approvals": unsafe_items,
    }


def format_markdown_report(analysis: dict, metadata: dict | None = None) -> str:
    """Generate Markdown report for evaluation results."""
    meta = metadata or {}
    ov = analysis["overall"]
    splits = analysis["splits"]
    muts = analysis["mutations"]
    unsafe = analysis["unsafe_approvals"]

    lines = [
        "# Antibody Verification Gate Evaluation Report",
        "",
        f"**Generated:** {meta.get('created_at', datetime.now(timezone.utc).isoformat())}",
        f"**Evaluated Split:** {meta.get('split', 'all')}",
        f"**Runs per memo:** {meta.get('runs', 1)}",
        f"**Total items:** {ov['total']}",
        "",
        "## Summary Metrics",
        "",
        "| Metric | Result | Target | Status |",
        "|---|---|---|---|",
        f"| **Unsafe approvals** | {ov['unsafe_approvals']} ({ov['unsafe_approval_rate']:.1f}%) | 0.0% | {'PASS' if ov['unsafe_approvals'] == 0 else 'FAIL'} |",
        f"| **Good memos stopped** | {ov['good_stopped']} ({ov['good_stopped_rate']:.1f}%) | < 5.0% | {'PASS' if ov['good_stopped_rate'] < 5.0 else 'FAIL'} |",
        f"| **Automation rate** | {ov['automation_rate']:.1f}% | High | N/A |",
        f"| **Stability (decision flips)** | {ov['changed_rate']:.1f}% | 0.0% | {'PASS' if ov['changed_decisions'] == 0 else 'FAIL'} |",
        f"| **Seconds per memo** | {ov['avg_seconds']:.3f}s | < 60s | {'PASS' if ov['avg_seconds'] < 60.0 else 'FAIL'} |",
        f"| **Weighted Cost** | **{ov['weighted_cost']}** (avg {ov['cost_per_item']:.2f}) | Lower is better | Baseline |",
        "",
        "> **Weighted cost formula:** `(unsafe_approvals * 10) + (false_blocks * 3) + (unnecessary_holds * 1)`",
        "",
        "## Breakdown by Split",
        "",
        "| Split | Total | Bad Memos | Unsafe Appr (%) | Good Memos | Good Stopped (%) | Automation | Flips | Avg Time | Cost |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    for s_name, s_m in splits.items():
        lines.append(
            f"| **{s_name}** | {s_m['total']} | {s_m['bad_count']} | "
            f"{s_m['unsafe_approvals']} ({s_m['unsafe_approval_rate']:.1f}%) | {s_m['good_count']} | "
            f"{s_m['good_stopped']} ({s_m['good_stopped_rate']:.1f}%) | {s_m['automation_rate']:.1f}% | "
            f"{s_m['changed_decisions']} ({s_m['changed_rate']:.1f}%) | {s_m['avg_seconds']:.3f}s | {s_m['weighted_cost']} |"
        )

    lines.extend([
        "",
        "## Breakdown by Mutation Type",
        "",
        "| Mutation Type | Items | Expected | Appr | Hold | Block | Unsafe Appr | Good Stopped | Cost |",
        "|---|---|---|---|---|---|---|---|---|",
    ])

    for m_name, m_m in muts.items():
        exp = "APPROVE" if m_m["bad_count"] == 0 else ("BLOCK / HOLD" if m_m["good_count"] == 0 else "MIXED")
        lines.append(
            f"| `{m_name}` | {m_m['total']} | {exp} | {m_m['approved']} | {m_m['held']} | {m_m['blocked']} | "
            f"{m_m['unsafe_approvals']} | {m_m['good_stopped']} | {m_m['weighted_cost']} |"
        )

    lines.extend([
        "",
        "## Unsafe Approvals (Bad Memos Approved by Gate)",
        "",
    ])

    if not unsafe:
        lines.append("*None! Zero unsafe approvals detected.*")
    else:
        lines.append(f"Found **{len(unsafe)} unsafe approvals**:")
        lines.append("")
        lines.append("| ID | Case | Mutation | Split | Reason Given by Gate | Memo Text |")
        lines.append("|---|---|---|---|---|---|")
        for u in unsafe:
            text_snippet = u['text'].replace('|', '\\|')
            reason_snippet = u['reason'].replace('|', '\\|')
            lines.append(f"| `{u['id']}` | {u['case'] or 'None'} | `{u['mutation']}` | {u['split']} | {reason_snippet} | {text_snippet} |")

    lines.append("")
    return "\n".join(lines)


def print_metrics_table(analysis: dict):
    """Print ASCII summary table to stdout."""
    ov = analysis["overall"]
    splits = analysis["splits"]
    muts = analysis["mutations"]
    unsafe = analysis["unsafe_approvals"]

    print("\n" + "=" * 80)
    print("                    ANTIBODY EVALUATION METRICS REPORT")
    print("=" * 80)
    print(f"Total Items Evaluated: {ov['total']}")
    print(f"Unsafe Approvals:      {ov['unsafe_approvals']}/{ov['bad_count']} ({ov['unsafe_approval_rate']:.1f}%) [TARGET: 0%]")
    print(f"Good Memos Stopped:    {ov['good_stopped']}/{ov['good_count']} ({ov['good_stopped_rate']:.1f}%) [TARGET: <5%]")
    print(f"Automation Rate:       {ov['automation_rate']:.1f}%")
    print(f"Stability Flips:       {ov['changed_decisions']}/{ov['total']} ({ov['changed_rate']:.1f}%)")
    print(f"Average Response Time: {ov['avg_seconds']:.4f}s")
    print(f"Total Weighted Cost:   {ov['weighted_cost']} (avg {ov['cost_per_item']:.2f} per memo)")
    print("-" * 80)

    print("\nBY SPLIT:")
    print(f"{'Split':<12} | {'Items':<6} | {'Unsafe Appr':<12} | {'Good Stopped':<12} | {'Automation':<10} | {'Cost':<6}")
    print("-" * 72)
    for s_name, s_m in splits.items():
        print(
            f"{s_name:<12} | {s_m['total']:<6} | "
            f"{s_m['unsafe_approvals']} ({s_m['unsafe_approval_rate']:.1f}%)".ljust(12) + " | "
            f"{s_m['good_stopped']} ({s_m['good_stopped_rate']:.1f}%)".ljust(12) + " | "
            f"{s_m['automation_rate']:.1f}%".ljust(10) + " | "
            f"{s_m['weighted_cost']:<6}"
        )

    print("\nBY MUTATION TYPE:")
    print(f"{'Mutation':<24} | {'Items':<5} | {'Appr':<5} | {'Hold':<5} | {'Blk':<5} | {'Unsafe':<6} | {'Cost':<5}")
    print("-" * 72)
    for m_name, m_m in muts.items():
        print(
            f"{m_name:<24} | {m_m['total']:<5} | {m_m['approved']:<5} | {m_m['held']:<5} | {m_m['blocked']:<5} | "
            f"{m_m['unsafe_approvals']:<6} | {m_m['weighted_cost']:<5}"
        )

    print("\nUNSAFE APPROVALS:")
    if not unsafe:
        print("  None (0 unsafe approvals)")
    else:
        for u in unsafe:
            print(f"  [UNSAFE APPROVAL] ID: {u['id']} | Case: {u['case']} | Mutation: {u['mutation']}")
            print(f"    Text:   {u['text']}")
            print(f"    Reason: {u['reason']}\n")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Compute evaluation metrics from results JSON")
    parser.add_argument("--results", default=str(DEFAULT_RESULTS), help="Path to results JSON")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Path to save report Markdown")
    parser.add_argument("--split", choices=["tune", "heldout", "all"], default="all", help="Filter by split")
    args = parser.parse_args()

    results_file = Path(args.results)
    if not results_file.exists():
        sys.exit(f"Results file not found at {results_file}. Run eval/run.py first.")

    raw_data = json.loads(results_file.read_text(encoding="utf-8"))
    items = raw_data.get("items", raw_data) if isinstance(raw_data, dict) else raw_data
    metadata = raw_data.get("metadata", {}) if isinstance(raw_data, dict) else {}

    if args.split != "all":
        items = [i for i in items if i.get("split") == args.split]
        metadata["split"] = args.split

    analysis = analyze_results(items)
    print_metrics_table(analysis)

    report_md = format_markdown_report(analysis, metadata=metadata)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_md, encoding="utf-8")
    print(f"Saved evaluation report to {out_path}")


if __name__ == "__main__":
    main()

