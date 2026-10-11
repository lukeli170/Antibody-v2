"""Pytest test suite for Antibody v2 Case Matcher (Phase 3)."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from antibody.matcher import CaseMatcher


def test_near_miss_citation_detection():
    matcher = CaseMatcher()
    # Mapp: 367 U.S. 643; near miss: 367 U.S. 634
    res = matcher.match_claim("Mapp v. Ohio", "367 U.S. 634", 1961)
    assert res.suggested_action == "BLOCK"
    assert res.citation_status == "NEAR_MISS"
    assert "Near-miss citation" in res.issues[0]

    # Gideon: 372 U.S. 335; near miss: 373 U.S. 335
    res = matcher.match_claim("Gideon v. Wainwright", "373 U.S. 335", 1963)
    assert res.suggested_action == "BLOCK"
    assert res.citation_status == "NEAR_MISS"


def test_wrong_year_detection():
    matcher = CaseMatcher()
    # Marbury: 1803; wrong year: 1813
    res = matcher.match_claim("Marbury v. Madison", "5 U.S. 137", 1813)
    assert res.suggested_action == "BLOCK"
    assert res.year_status == "MISMATCH"
    assert "Year mismatch" in res.issues[0]


def test_short_name_linking():
    matcher = CaseMatcher()
    # Short name Gideon -> Gideon v. Wainwright
    res = matcher.match_claim("Gideon", "372 U.S. 335", 1963)
    assert res.status == "TRUSTED_MATCH"
    assert res.canonical_case == "Gideon v. Wainwright"
    assert res.suggested_action == "PROCEED"


def test_fabricated_case_detection():
    matcher = CaseMatcher()
    # Varghese full name
    res = matcher.match_claim("Varghese v. China Southern Airlines", None, None)
    assert res.status == "FABRICATED_MATCH"
    assert res.suggested_action == "BLOCK"

    # Shaboon short name
    res2 = matcher.match_claim("Shaboon", None, None)
    assert res2.status == "FABRICATED_MATCH"
    assert res2.suggested_action == "BLOCK"


def test_unverified_case():
    matcher = CaseMatcher()
    res = matcher.match_claim("Harlan v. Pinecrest Mutual", "288 F.3d 1104", 2002)
    assert res.status == "UNVERIFIED"
    assert res.suggested_action == "HOLD"

