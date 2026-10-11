"""Unit tests for Antibody v2 evaluation metrics calculation."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from eval.metrics import compute_group_metrics, analyze_results, format_markdown_report


def test_empty_metrics():
    res = compute_group_metrics([])
    assert res["total"] == 0
    assert res["unsafe_approvals"] == 0
    assert res["weighted_cost"] == 0
    assert res["automation_rate"] == 0.0


def test_weighted_cost_and_rates():
    # 2 bad memos: 1 unsafe approval (APPROVE), 1 correctly blocked (BLOCK)
    # 3 good memos: 1 correct (APPROVE), 1 false block (BLOCK), 1 unnecessary hold (HOLD_FOR_REVIEW)
    items = [
        {"id": "b1", "label": "bad", "expected_decision": "BLOCK", "decision": "APPROVE"},
        {"id": "b2", "label": "bad", "expected_decision": "BLOCK", "decision": "BLOCK"},
        {"id": "g1", "label": "good", "expected_decision": "APPROVE", "decision": "APPROVE"},
        {"id": "g2", "label": "good", "expected_decision": "APPROVE", "decision": "BLOCK"},
        {"id": "g3", "label": "good", "expected_decision": "APPROVE", "decision": "HOLD_FOR_REVIEW"},
    ]

    metrics = compute_group_metrics(items)

    assert metrics["total"] == 5
    assert metrics["bad_count"] == 2
    assert metrics["good_count"] == 3

    # Unsafe approval: 1 out of 2 bad items -> 50%
    assert metrics["unsafe_approvals"] == 1
    assert metrics["unsafe_approval_rate"] == 50.0

    # Good stopped: 2 out of 3 good items (1 block, 1 hold) -> 66.67%
    assert metrics["good_stopped"] == 2
    assert metrics["false_blocks"] == 1
    assert metrics["unnecessary_holds"] == 1
    assert round(metrics["good_stopped_rate"], 2) == 66.67

    # Automation rate: 4 out of 5 items not held (b1, b2, g1, g2) -> 80%
    assert metrics["automation_rate"] == 80.0

    # Weighted cost:
    # 1 unsafe approval * 10 = 10
    # 1 false block * 3 = 3
    # 1 unnecessary hold * 1 = 1
    # Total = 14
    assert metrics["weighted_cost"] == 14
    assert metrics["cost_per_item"] == 2.8


def test_stability_detection():
    items = [
        {
            "id": "item1",
            "label": "good",
            "decision": "APPROVE",
            "runs": [
                {"decision": "APPROVE"},
                {"decision": "APPROVE"},
            ],
            "changed": False,
        },
        {
            "id": "item2",
            "label": "bad",
            "decision": "BLOCK",
            "runs": [
                {"decision": "BLOCK"},
                {"decision": "APPROVE"},
            ],
            "changed": True,
        },
    ]

    metrics = compute_group_metrics(items)
    assert metrics["changed_decisions"] == 1
    assert metrics["changed_rate"] == 50.0


def test_analyze_results_by_split_and_mutation():
    items = [
        {
            "id": "m1",
            "case": "Miranda v. Arizona",
            "mutation": "swapped_requirement",
            "split": "tune",
            "label": "bad",
            "expected_decision": "HOLD_FOR_REVIEW",
            "decision": "APPROVE",
            "reason": "Approved",
            "text": "Miranda requires a warrant",
        },
        {
            "id": "m2",
            "case": "Miranda v. Arizona",
            "mutation": "exact_holding",
            "split": "tune",
            "label": "good",
            "expected_decision": "APPROVE",
            "decision": "APPROVE",
            "reason": "Approved",
            "text": "Miranda exact",
        },
        {
            "id": "m3",
            "case": "Mapp v. Ohio",
            "mutation": "negation",
            "split": "heldout",
            "label": "bad",
            "expected_decision": "BLOCK",
            "decision": "BLOCK",
            "reason": "Reversed",
            "text": "Mapp negation",
        },
    ]

    analysis = analyze_results(items)

    assert "tune" in analysis["splits"]
    assert "heldout" in analysis["splits"]
    assert analysis["splits"]["tune"]["unsafe_approvals"] == 1
    assert analysis["splits"]["heldout"]["unsafe_approvals"] == 0

    assert "swapped_requirement" in analysis["mutations"]
    assert analysis["mutations"]["swapped_requirement"]["unsafe_approvals"] == 1

    assert len(analysis["unsafe_approvals"]) == 1
    assert analysis["unsafe_approvals"][0]["id"] == "m1"
    assert analysis["unsafe_approvals"][0]["case"] == "Miranda v. Arizona"


def test_markdown_report_formatting():
    items = [
        {
            "id": "miranda-swapped",
            "case": "Miranda v. Arizona",
            "mutation": "swapped_requirement",
            "split": "tune",
            "label": "bad",
            "expected_decision": "HOLD_FOR_REVIEW",
            "decision": "APPROVE",
            "reason": "No issues found",
            "text": "Miranda requires a warrant",
        }
    ]
    analysis = analyze_results(items)
    report = format_markdown_report(analysis)

    assert "# Antibody Verification Gate Evaluation Report" in report
    assert "Unsafe approvals" in report
    assert "Miranda v. Arizona" in report
    assert "miranda-swapped" in report
    assert "Miranda requires a warrant" in report

