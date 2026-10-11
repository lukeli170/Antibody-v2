"""Case matcher for Antibody v2.

Links each claim's case to trusted_citations.json or known_fabricated.json:
- Name cleanup (short names, 'v.' vs 'vs.', corporate suffixes)
- Fuzzy name matching with rapidfuzz (ambiguous matches fall to HOLD)
- Citation normalization and edit-distance near-miss detection
- Year verification
- Fabricated case detection (BLOCK)
- Unverified case detection (HOLD)
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path
from rapidfuzz import fuzz, distance

REPO = Path(__file__).resolve().parent.parent
PARALEGAL_DIR = REPO / "personas" / "paralegal"

V = r"(?:v|vs|versus)\.?"
CORPORATE_WORDS = {"co", "inc", "corp", "ltd", "llc", "company", "corporation", "railroad", "railway", "rr", "r.r"}
GENERIC_FIRST = {"new", "united", "the", "state", "people", "city", "county", "commonwealth", "in", "ex"}


@dataclass
class MatchResult:
    status: str            # "TRUSTED_MATCH", "FABRICATED_MATCH", "UNVERIFIED", "AMBIGUOUS", "NO_CASE"
    canonical_case: str | None = None
    trusted_entry: dict | None = None
    citation_status: str = "MATCH"    # "MATCH", "NEAR_MISS", "MISMATCH", "UNSTATED"
    year_status: str = "MATCH"        # "MATCH", "MISMATCH", "UNSTATED"
    issues: list[str] = None          # List of concrete discrepancies
    suggested_action: str = "PROCEED" # "PROCEED", "BLOCK", "HOLD"

    def __post_init__(self):
        if self.issues is None:
            self.issues = []


def normalize_whitespace_punct(text: str) -> str:
    t = text.lower().replace("’", "'").replace(".", " ")
    t = re.sub(r"\bvs\b|\bversus\b", "v", t)
    return re.sub(r"\s+", " ", t).strip()


def normalize_citation(cite: str | None) -> str | None:
    if not cite:
        return None
    # Normalize 384 U.S. 436, 384 U. S. 436, etc.
    c = cite.strip().replace("’", "'")
    c = re.sub(r"\s+", " ", c)
    c = re.sub(r"U\.\s?S\.", "U.S.", c)
    c = re.sub(r"N\.\s?Y\.", "N.Y.", c)
    return c


def extract_short_names(case_name: str) -> list[str]:
    """Return distinctive short forms for a case name."""
    first = re.split(rf"\s+{V}\s+", case_name, maxsplit=1)[0].strip()
    words = [w.strip(" ,.") for w in first.split() if w.strip(" ,.")]
    while len(words) > 1 and words[-1].lower() in CORPORATE_WORDS:
        words.pop()
    names = [" ".join(words)]
    if len(words) > 1 and words[0].lower() not in GENERIC_FIRST:
        names.append(words[0])
    return names


class CaseMatcher:
    def __init__(self):
        self.trusted_cases = []
        self.fabricated_cases = []
        self._load_lists()

    def _load_lists(self):
        t_file = PARALEGAL_DIR / "trusted_citations.json"
        if t_file.exists():
            self.trusted_cases = json.loads(t_file.read_text(encoding="utf-8")).get("cases", [])
        f_file = PARALEGAL_DIR / "known_fabricated.json"
        if f_file.exists():
            self.fabricated_cases = json.loads(f_file.read_text(encoding="utf-8")).get("cases", [])

    def find_case_match(self, written_name: str) -> tuple[str, dict | None, str | None]:
        """Match written case name to trusted or fabricated lists.
        Returns (list_type, entry, match_case_name).
        list_type is 'fabricated', 'trusted', 'ambiguous', or 'unknown'.
        """
        if not written_name or not written_name.strip():
            return "unknown", None, None

        w_clean = normalize_whitespace_punct(written_name)
        w_words = set(w_clean.split())

        # 1. Exact match check
        for e in self.fabricated_cases:
            if normalize_whitespace_punct(e["case"]) == w_clean:
                return "fabricated", e, e["case"]
            for sn in extract_short_names(e["case"]):
                if normalize_whitespace_punct(sn) == w_clean:
                    return "fabricated", e, e["case"]

        for e in self.trusted_cases:
            if normalize_whitespace_punct(e["case"]) == w_clean:
                return "trusted", e, e["case"]
            for sn in extract_short_names(e["case"]):
                if normalize_whitespace_punct(sn) == w_clean:
                    return "trusted", e, e["case"]

        # 2. Fuzzy match against all candidates
        candidates = []
        for e in self.fabricated_cases:
            score = fuzz.token_sort_ratio(w_clean, normalize_whitespace_punct(e["case"]))
            if score >= 85:
                candidates.append(("fabricated", e, score))
            else:
                for sn in extract_short_names(e["case"]):
                    if fuzz.ratio(w_clean, normalize_whitespace_punct(sn)) >= 85:
                        candidates.append(("fabricated", e, 90))

        for e in self.trusted_cases:
            score = fuzz.token_sort_ratio(w_clean, normalize_whitespace_punct(e["case"]))
            if score >= 85:
                candidates.append(("trusted", e, score))
            else:
                for sn in extract_short_names(e["case"]):
                    if fuzz.ratio(w_clean, normalize_whitespace_punct(sn)) >= 85:
                        candidates.append(("trusted", e, 90))

        if not candidates:
            return "unknown", None, None

        # Sort by match score
        candidates.sort(key=lambda x: -x[2])
        top_type, top_entry, top_score = candidates[0]

        # Safety rule: if top two matches are equally strong for different cases, flag ambiguous
        if len(candidates) > 1 and candidates[1][2] == top_score and candidates[1][1]["case"] != top_entry["case"]:
            return "ambiguous", None, None

        return top_type, top_entry, top_entry["case"]

    def check_citation(self, stated_cite: str | None, trusted_cite: str) -> tuple[str, str | None]:
        """Check stated citation against trusted citation.
        Returns (status, detail). status is 'MATCH', 'NEAR_MISS', or 'MISMATCH'.
        """
        if not stated_cite:
            return "UNSTATED", None

        s_norm = normalize_citation(stated_cite)
        t_norm = normalize_citation(trusted_cite)

        if s_norm == t_norm:
            return "MATCH", None

        # Check edit distance / digit swap
        edit_dist = distance.Levenshtein.distance(s_norm, t_norm)
        # Check if digits were swapped or off by 1-2 characters
        if edit_dist <= 3:
            return "NEAR_MISS", f"Near-miss citation '{stated_cite}'; trusted is '{trusted_cite}' (edit distance {edit_dist})"

        return "MISMATCH", f"Citation mismatch '{stated_cite}'; trusted is '{trusted_cite}'"

    def match_claim(
        self,
        case_name: str | None,
        citation: str | None,
        year: int | None,
        is_public_law: bool = False,
    ) -> MatchResult:
        """Fully verify case identity, citation, and year against firm lists."""
        if is_public_law or not case_name:
            return MatchResult(
                status="NO_CASE",
                suggested_action="PROCEED",
            )

        list_type, entry, canonical = self.find_case_match(case_name)

        if list_type == "ambiguous":
            return MatchResult(
                status="AMBIGUOUS",
                issues=[f"Case name '{case_name}' is ambiguous and matches multiple entries"],
                suggested_action="HOLD",
            )

        if list_type == "fabricated":
            return MatchResult(
                status="FABRICATED_MATCH",
                canonical_case=canonical,
                issues=[f"Case '{canonical}' is flagged as fabricated in known_fabricated.json"],
                suggested_action="BLOCK",
            )

        if list_type == "unknown":
            return MatchResult(
                status="UNVERIFIED",
                canonical_case=case_name,
                issues=[f"Case '{case_name}' is not found in trusted or fabricated lists"],
                suggested_action="HOLD",
            )

        # Matched trusted list
        issues = []
        cite_status, cite_issue = "MATCH", None
        if citation and "citation" in entry:
            cite_status, cite_issue = self.check_citation(citation, entry["citation"])
            if cite_issue:
                issues.append(cite_issue)

        year_status = "MATCH"
        if year is not None and "year" in entry:
            if int(year) != int(entry["year"]):
                year_status = "MISMATCH"
                issues.append(f"Year mismatch: stated ({year}), trusted is ({entry['year']})")

        suggested_action = "PROCEED"
        if cite_status in ("NEAR_MISS", "MISMATCH") or year_status == "MISMATCH":
            suggested_action = "BLOCK"

        return MatchResult(
            status="TRUSTED_MATCH",
            canonical_case=canonical,
            trusted_entry=entry,
            citation_status=cite_status,
            year_status=year_status,
            issues=issues,
            suggested_action=suggested_action,
        )

