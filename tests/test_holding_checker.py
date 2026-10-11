"""Pytest test suite for Antibody v2 Holding Checker (Phase 4)."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from antibody.holding_checker import HoldingChecker
from antibody.matcher import CaseMatcher


def test_supported_exact_holding():
    matcher = CaseMatcher()
    checker = HoldingChecker()
    match = matcher.match_claim("Miranda v. Arizona", "384 U.S. 436", 1966)
    verdict = checker.verify_holding(
        "statements from custodial interrogation are inadmissible unless the suspect was first warned of their rights",
        match.canonical_case,
        match.trusted_entry,
    )
    assert verdict.verdict == "SUPPORTED"
    assert verdict.suggested_action == "PROCEED"


def test_supported_faithful_paraphrase():
    matcher = CaseMatcher()
    checker = HoldingChecker()
    match = matcher.match_claim("Gideon v. Wainwright", "372 U.S. 335", 1963)
    verdict = checker.verify_holding(
        "the Sixth Amendment guarantees appointed legal representation for indigent defendants in state felony trials",
        match.canonical_case,
        match.trusted_entry,
    )
    assert verdict.verdict == "SUPPORTED"
    assert verdict.suggested_action == "PROCEED"


def test_contradicted_negation():
    matcher = CaseMatcher()
    checker = HoldingChecker()
    match = matcher.match_claim("Miranda v. Arizona", "384 U.S. 436", 1966)
    verdict = checker.verify_holding(
        "statements obtained during custodial interrogation are admissible even if the suspect was never warned",
        match.canonical_case,
        match.trusted_entry,
    )
    assert verdict.verdict == "CONTRADICTED"
    assert verdict.suggested_action == "BLOCK"


def test_swapped_requirement_unrelated():
    matcher = CaseMatcher()
    checker = HoldingChecker()
    # The Miranda requires a warrant bug!
    match = matcher.match_claim("Miranda v. Arizona", "384 U.S. 436", 1966)
    verdict = checker.verify_holding(
        "police interrogation of a suspect in custody requires a search warrant",
        match.canonical_case,
        match.trusted_entry,
    )
    assert verdict.verdict == "UNRELATED"
    assert verdict.suggested_action == "HOLD"
    assert "warrant" in verdict.explanation


def test_wrong_case_swap_blocked():
    matcher = CaseMatcher()
    checker = HoldingChecker()
    # Gideon attached to Mapp's holding
    match = matcher.match_claim("Gideon v. Wainwright", "372 U.S. 335", 1963)
    verdict = checker.verify_holding(
        "the exclusionary rule applies to the states: evidence from unconstitutional searches is inadmissible",
        match.canonical_case,
        match.trusted_entry,
    )
    assert verdict.verdict == "WRONG_CASE"
    assert verdict.suggested_action == "BLOCK"
    assert verdict.other_case_match == "Mapp v. Ohio"


def test_dropped_exception_blocked():
    matcher = CaseMatcher()
    checker = HoldingChecker()
    match = matcher.match_claim("Brandenburg v. Ohio", "395 U.S. 444", 1969)
    verdict = checker.verify_holding(
        "advocacy of unlawful acts is always prohibited with no exceptions",
        match.canonical_case,
        match.trusted_entry,
    )
    assert verdict.verdict == "CONTRADICTED"
    assert verdict.suggested_action == "BLOCK"

