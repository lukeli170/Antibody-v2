"""Triage engine for Antibody v2.

Determines the verification tier for a memo before expensive checks run:
- Tier 0: Routine memo with no case names, citations, or legal statements.
- Tier 1: Public-law constitutional statements without case citations.
- Tier 2: Case citations with no stated holding.
- Tier 3: Stated holdings, multiple cases, or advocacy language (full pipeline).

Safety Rules:
1. Triage can only raise a tier, never lower it. Any citation pattern raises tier to at least 2.
2. Triage predicts claim count, which is verified by the claim splitter.
"""
import re
from dataclasses import dataclass

CITATION_PATTERN = re.compile(
    r"\b(?:v\.?|vs\.?)\b|\bU\.?\s?S\.?\b|\bF\.(?:2d|3d|Supp)?\b|\bN\.Y\.\b|\b\d{1,4}\s+[A-Za-z.\s]+\s+\d{1,6}\b",
    re.I,
)

PUBLIC_LAW_PATTERN = re.compile(
    r"\b(?:The\s+)?(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|Fourteenth|\d+th)\s+Amendment\b|\bEqual\s+Protection\s+Clause\b|\bDue\s+Process\s+Clause\b",
    re.I,
)

HOLDING_PATTERN = re.compile(
    r"\b(?:held\s+that|holds\s+that|holding\s+that|ruled\s+that|rules\s+that|established\s+that|"
    r"stands\s+for|requires\s+|prohibits\s+|allows\s+|permits\s+|excludes\s+|guarantees\s+|mandates\s+|bars\s+)",
    re.I,
)

ADVOCACY_PATTERN = re.compile(
    r"\b(?:slam\s+dunk|clearly|obviously|without\s+a\s+doubt|court\s+will\s+absolutely\s+agree|amazing\s+news)\b|!{2,}",
    re.I,
)


@dataclass
class TriageResult:
    tier: int                     # 0, 1, 2, or 3
    predicted_claims: int
    has_citations: bool
    has_holdings: bool
    has_public_law: bool
    has_advocacy: bool
    rationale: str


def triage_memo(text: str) -> TriageResult:
    """Analyze memo text and determine processing tier."""
    has_cit = bool(CITATION_PATTERN.search(text))
    has_pl = bool(PUBLIC_LAW_PATTERN.search(text))
    has_hold = bool(HOLDING_PATTERN.search(text))
    has_adv = bool(ADVOCACY_PATTERN.search(text))

    # Approximate claim count prediction
    v_count = len(re.findall(r"\b(?:v\.?|vs\.?)\b", text, re.I))
    pl_count = len(PUBLIC_LAW_PATTERN.findall(text))
    predicted_claims = max(v_count + pl_count, 1 if (has_cit or has_pl) else 0)

    # Base tier determination
    if not has_cit and not has_pl and not has_hold and not has_adv:
        tier = 0
        rationale = "Tier 0: Routine text with no citations, holdings, or advocacy."
    elif has_pl and not has_cit:
        tier = 1
        rationale = "Tier 1: Public-law constitutional claim without case citation."
    elif has_cit and not has_hold and not has_adv:
        tier = 2
        rationale = "Tier 2: Case citation without stated holding."
    else:
        tier = 3
        rationale = "Tier 3: Stated holding, multiple citations, or advocacy requiring full checking."

    # Safety rule: Triage can only raise a tier, never lower it.
    if has_cit and tier < 2:
        tier = 2
        rationale += " [Raised to Tier 2 by citation safety rule]"
    if (has_hold or has_adv or predicted_claims > 1) and tier < 3:
        tier = 3
        rationale += " [Raised to Tier 3 by holding/advocacy safety rule]"

    return TriageResult(
        tier=tier,
        predicted_claims=predicted_claims,
        has_citations=has_cit,
        has_holdings=has_hold,
        has_public_law=has_pl,
        has_advocacy=has_adv,
        rationale=rationale,
    )

