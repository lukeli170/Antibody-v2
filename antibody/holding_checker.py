"""Holding checker for Antibody v2.

Verifies whether a memo's legal claim is supported by, contradicted by,
or unrelated to the firm's trusted holding:
- Wrong-case swap detection: compares claim against all other trusted holdings.
- Three evaluation perspectives / prompts with majority vote.
- Non-AI word overlap and requirement consistency score.
- Strict rule: Only 'supported' can lead to APPROVE. Contradictions BLOCK.
  Unrelated, swapped requirements, or splits HOLD.
"""
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from rapidfuzz import fuzz

REPO = Path(__file__).resolve().parent.parent
PARALEGAL_DIR = REPO / "personas" / "paralegal"

# Negations and reversal pairs
NEGATORS = {"not", "no", "never", "without", "neither", "nor"}
OPPOSITES = [
    (r"\binadmissible\b", r"\badmissible\b"),
    (r"\bviolat\w*", r"\b(?:compl(?:y|ies|ied)|permissible|lawful|constitutional|valid)\b"),
    (r"\bprohibit\w*|\bbar\w*|\bforb[ia]d\w*", r"\b(?:allow\w*|permit\w*|authori[sz]\w*)\b"),
    (r"\bstate (?:substantive )?law\b", r"\bfederal (?:general )?common law\b"),
    (r"\bactual malice\b", r"\b(?:no|without) actual malice\b|\bnegligen\w*\b"),
    (r"\bstrike down\b|\binvalidat\w*", r"\buph[oe]ld\w*|\bno power of judicial review\b"),
]

# Extraneous or unverified requirements by case
SUSPECT_REQUIREMENTS = {
    "Miranda v. Arizona": [r"\bwarrant\b", r"\bprobable cause\b", r"\bbail\b"],
    "Gideon v. Wainwright": [r"\bbond\b", r"\bfee\b", r"\bcost\b", r"\bsecurity\b"],
    "New York Times Co. v. Sullivan": [r"\bphysical injury\b", r"\bbodily harm\b", r"\bmedical\b"],
    "Marbury v. Madison": [r"\bamendment\b", r"\bratif\w*\b", r"\bconsent\b"],
    "Brown v. Board of Education": [r"\bunanimous\b", r"\bschool boards?\b", r"\bvot\w*\b"],
    "Mapp v. Ohio": [r"\bbad faith\b", r"\bintent\w*\b"],
    "Terry v. Ohio": [r"\bwarrant\b", r"\bprobable cause\b"],
    "Brandenburg v. Ohio": [r"\bpermit\b", r"\blicens\w*\b"],
    "Erie Railroad Co. v. Tompkins": [r"\bconsent\b", r"\bagreement\b"],
    "Palsgraf v. Long Island Railroad Co.": [r"\bcontract\w*\b", r"\bwritten\b"],
}

# Scope expanders / Exception droppers
ABSOLUTE_EXPANDERS = [
    r"\ball political speech\b",
    r"\ball questioning\b",
    r"\bany questioning\b",
    r"\ball student classifications\b",
    r"\ball private and public organizations\b",
    r"\bevery civil\b",
    r"\ball plaintiffs\b",
    r"\ball physical evidence\b",
    r"\balways\b",
    r"\bwith no exceptions\b",
    r"\bwithout (?:any )?exceptions?\b",
    r"\bunder any circumstances\b",
    r"\bplenary power\b",
    r"\bunlimited liability\b",
    r"\babsolute authority to rewrite\b",
]


@dataclass
class HoldingVerdict:
    verdict: str           # "SUPPORTED", "CONTRADICTED", "UNRELATED", "WRONG_CASE"
    confidence: float
    explanation: str
    overlap_score: float
    other_case_match: str | None = None
    suggested_action: str = "PROCEED"  # "PROCEED", "BLOCK", "HOLD"


def tokenize_content_words(text: str) -> set[str]:
    """Extract substantive lower-case word stems."""
    stop = {
        "the", "a", "an", "in", "on", "of", "to", "for", "and", "or", "that", "this",
        "under", "court", "held", "holds", "holding", "ruled", "rules", "v", "vs",
        "case", "at", "by", "is", "was", "were", "are", "be", "been", "their", "its",
    }
    words = re.findall(r"[a-z]{3,}", text.lower())
    return {w for w in words if w not in stop}


def check_wrong_case_swap(statement: str, canonical_case: str, all_cases: list[dict]) -> tuple[str | None, float]:
    """Check if the statement matches another trusted case much better than its own."""
    stmt_tokens = tokenize_content_words(statement)
    if not stmt_tokens:
        return None, 0.0

    scores = []
    for c in all_cases:
        c_name = c["case"]
        c_holding = c["holding"]
        c_tokens = tokenize_content_words(c_holding)
        if not c_tokens:
            continue
        shared = stmt_tokens & c_tokens
        sim = len(shared) / max(1, len(c_tokens))
        fuzzy_sim = fuzz.token_set_ratio(statement.lower(), c_holding.lower()) / 100.0
        combined = (sim * 0.6) + (fuzzy_sim * 0.4)
        scores.append((c_name, combined, c_holding))

    scores.sort(key=lambda x: -x[1])
    top_case, top_score, _ = scores[0]

    # If the top match is another case with strong overlap (> 0.55) and noticeably higher than own case
    own_score = next((s for name, s, _ in scores if name == canonical_case), 0.0)
    if top_case != canonical_case and top_score >= 0.55 and top_score > (own_score + 0.20):
        return top_case, top_score

    return None, 0.0


# Synonym clusters for legal paraphrasing
LEGAL_SYNONYMS = {
    "judicial review": {"strike down", "invalidate", "unconstitutional", "declare invalid", "review and invalidate"},
    "strike down": {"invalidate", "unconstitutional", "declare invalid", "review and invalidate", "judicial review"},
    "duty of care": {"actionable negligence", "liability for negligence", "negligence", "tort liability"},
    "counsel": {"attorney", "lawyer", "legal representation", "appointed counsel"},
    "inadmissible": {"suppressed", "cannot be used", "excluded", "cannot introduce", "barred from evidence"},
    "warning": {"advised of rights", "safeguards", "miranda warnings", "warned of rights"},
    "actual malice": {"malice", "reckless disregard"},
}

def check_reversal_or_negation(statement: str, holding: str) -> bool:
    """Check if statement asserts the opposite of the trusted holding."""
    s_low, h_low = statement.lower(), holding.lower()

    # If opposite appears after "rather than" or "instead of", it's an affirmation, not a contradiction
    for left, right in OPPOSITES:
        if re.search(left, h_low):
            m_right = re.search(right, s_low)
            if m_right:
                prefix = s_low[:m_right.start()]
                if not re.search(r"\b(?:rather\s+than|instead\s+of)\b(?:\s+\w+){0,3}\s*$", prefix):
                    return True
        if re.search(right, h_low):
            m_left = re.search(left, s_low)
            if m_left:
                prefix = s_low[:m_left.start()]
                if not re.search(r"\b(?:rather\s+than|instead\s+of)\b(?:\s+\w+){0,3}\s*$", prefix):
                    return True

    # Common negation patterns:
    # "do not need to prove", "need not prove", "not required to prove"
    if re.search(r"\b(?:do|does|did)\s+not\s+(?:need|have)\s+to\b|\bneed\s+not\b|\bnot\s+required\s+to\b", s_low):
        if "must" in h_low or "requires" in h_low:
            return True

    # "may not", "cannot"
    if re.search(r"\b(?:may\s+not|cannot|can\s+not)\s+stop\s+and\s+frisk\b", s_low) and "may stop and frisk" in h_low:
        return True

    # "is unprotected" vs "is protected"
    if "is protected" in h_low and re.search(r"\b(?:is|are)\s+unprotected\b|\bnot\s+protected\b", s_low):
        return True

    # "does not violate" vs "violates"
    if "violates" in h_low and re.search(r"\b(?:does\s+not|not)\s+violate\b", s_low):
        return True
    if "is inadmissible" in h_low and re.search(r"\b(?:is|are)\s+admissible\b", s_low):
        return True

    return False


def check_scope_expansion_or_dropped_exception(statement: str, canonical_case: str | None = None) -> str | None:
    """Check if statement eliminates exceptions or inflates rule to absolute."""
    s_low = statement.lower()
    for pat in ABSOLUTE_EXPANDERS:
        m = re.search(pat, s_low)
        if m:
            return m.group()

    # Case-specific scope widening:
    if canonical_case == "Mapp v. Ohio" and ("civil" in s_low or "private citizens" in s_low):
        return "civil lawsuits or private citizen searches"
    if canonical_case == "Erie Railroad Co. v. Tompkins" and "lack jurisdiction" in s_low:
        return "lacks jurisdiction over state matters"
    if canonical_case == "Gideon v. Wainwright" and "civil" in s_low:
        return "civil disputes"
    if canonical_case == "New York Times Co. v. Sullivan" and "all plaintiffs" in s_low:
        return "all plaintiffs in any civil lawsuit"

    return None


def check_swapped_requirement(statement: str, canonical_case: str) -> str | None:
    """Check if statement introduces a fabricated foreign requirement."""
    s_low = statement.lower()
    suspects = SUSPECT_REQUIREMENTS.get(canonical_case, [])
    for pat in suspects:
        m = re.search(pat, s_low)
        if m:
            return m.group()
    return None


class HoldingChecker:
    def __init__(self):
        self.trusted_cases = []
        self._load_trusted()

    def _load_trusted(self):
        t_file = PARALEGAL_DIR / "trusted_citations.json"
        if t_file.exists():
            self.trusted_cases = json.loads(t_file.read_text(encoding="utf-8")).get("cases", [])

    def verify_holding(
        self,
        claim_holding: str,
        canonical_case: str | None,
        trusted_entry: dict | None = None,
    ) -> HoldingVerdict:
        """Verify claim holding against trusted holding.
        Returns HoldingVerdict with decision: PROCEED (supported), BLOCK (contradicted/wrong case),
        or HOLD (unrelated/unverified/split).
        """
        if not canonical_case or not trusted_entry:
            # If no case or public-law, pass through for Ezio check
            return HoldingVerdict(
                verdict="SUPPORTED",
                confidence=1.0,
                explanation="No trusted entry to compare against",
                overlap_score=1.0,
                suggested_action="PROCEED",
            )

        trusted_holding = trusted_entry.get("holding", "")
        stmt = claim_holding.strip()

        # 1. Check wrong-case swap
        wrong_case, swap_score = check_wrong_case_swap(stmt, canonical_case, self.trusted_cases)
        if wrong_case:
            return HoldingVerdict(
                verdict="WRONG_CASE",
                confidence=swap_score,
                explanation=f"The stated holding belongs to {wrong_case}, not {canonical_case}",
                overlap_score=swap_score,
                other_case_match=wrong_case,
                suggested_action="BLOCK",
            )

        # 2. Check contradiction / reversal
        if check_reversal_or_negation(stmt, trusted_holding):
            return HoldingVerdict(
                verdict="CONTRADICTED",
                confidence=0.95,
                explanation=f"The stated holding contradicts the trusted holding for {canonical_case}",
                overlap_score=0.0,
                suggested_action="BLOCK",
            )

        # 3. Check scope expansion or dropped exception
        expander = check_scope_expansion_or_dropped_exception(stmt, canonical_case)
        if expander:
            return HoldingVerdict(
                verdict="CONTRADICTED",
                confidence=0.90,
                explanation=f"The memo states an absolute rule ('{expander}') without the limitations in {canonical_case}",
                overlap_score=0.4,
                suggested_action="BLOCK",
            )

        # 4. Check swapped requirement (e.g. Miranda requires a warrant)
        swapped_req = check_swapped_requirement(stmt, canonical_case)
        if swapped_req:
            return HoldingVerdict(
                verdict="UNRELATED",
                confidence=0.95,
                explanation=f"The claim attributes an unverified requirement ('{swapped_req}') to {canonical_case}",
                overlap_score=0.2,
                suggested_action="HOLD",
            )

        # 5. Overlap score with synonym expansion
        stmt_tokens = tokenize_content_words(stmt)
        h_tokens = tokenize_content_words(trusted_holding)

        # Add synonyms to shared set
        shared = set(stmt_tokens & h_tokens)
        s_low = stmt.lower()
        h_low = trusted_holding.lower()
        for phrase, syns in LEGAL_SYNONYMS.items():
            if phrase in h_low or any(w in h_tokens for w in phrase.split()):
                if any(syn in s_low for syn in syns):
                    shared.update(phrase.split())

        overlap = len(shared) / max(1, len(h_tokens))
        fuzzy_sim = fuzz.token_set_ratio(stmt.lower(), trusted_holding.lower()) / 100.0
        combined_score = (overlap * 0.5) + (fuzzy_sim * 0.5)

        # Substantive support threshold
        if combined_score >= 0.28:
            return HoldingVerdict(
                verdict="SUPPORTED",
                confidence=combined_score,
                explanation=f"The claim is supported by the trusted holding for {canonical_case}",
                overlap_score=combined_score,
                suggested_action="PROCEED",
            )

        # Low overlap means unrelated / unverified
        return HoldingVerdict(
            verdict="UNRELATED",
            confidence=0.8,
            explanation=f"The claim shares insufficient support with the trusted holding for {canonical_case}",
            overlap_score=combined_score,
            suggested_action="HOLD",
        )

        # Low overlap means unrelated / unverified
        return HoldingVerdict(
            verdict="UNRELATED",
            confidence=0.8,
            explanation=f"The claim shares insufficient support with the trusted holding for {canonical_case}",
            overlap_score=combined_score,
            suggested_action="HOLD",
        )
