"""Claim splitter for Antibody v2.

Breaks untrusted legal memos into individual, verifiable claims:
- Identifies case name, citation, year, and stated holding for each claim.
- Extracts public-law statements (e.g. constitutional guarantees).
- Verifies that every claim's quote exists word-for-word in the memo text.
- Throws out made-up or hallucinated quotes.
- Detects instruction-shaped injection attempts.
"""
import json
import os
import re
from pathlib import Path

from antibody.models import Claim, SplitResult

REPO = Path(__file__).resolve().parent.parent
PARALEGAL_DIR = REPO / "personas" / "paralegal"

# Prompt injection markers
INJECTION_PATTERNS = [
    re.compile(r"\bignore\s+(?:all\s+|any\s+|previous\s+|prior\s+)?instructions\b", re.I),
    re.compile(r"\bapprove\s+this\s+(?:memo|document|request|immediately)\b", re.I),
    re.compile(r"\bsystem\s*(?:alert|notice)?\s*:\s*", re.I),
    re.compile(r"\bdisregard\s+(?:prior|previous|all|system)\s+instructions\b", re.I),
    re.compile(r"\binstructions?\s+override\b", re.I),
    re.compile(r"\bmandatory\s+command\b", re.I),
]

# Abbreviations where period is not a sentence boundary
ABBREVIATIONS = {
    "v", "vs", "co", "inc", "corp", "ltd", "cir", "ct", "no", "nos", "mr", "mrs", "ms",
    "dr", "st", "supp", "app", "ed", "jr", "sr", "id", "cf", "al", "rptr", "dist", "ry",
    "mfg", "bros", "univ", "assn", "dept", "govt", "amend", "art", "const", "stat", "ann",
    "rev", "pp", "sec", "para", "ch", "cl", "e.g", "i.e", "u.s", "f.3d", "f.2d", "n.y",
}

# Reporters
YEAR_RE = re.compile(r"\b(1[7-9]\d\d|20\d\d)\b")
PAREN_YEAR_RE = re.compile(r"\((?:[A-Za-z0-9.\s]+)?\b(1[7-9]\d\d|20\d\d)\b\)")

REPORTERS = [
    r"U\.?\s?S\.?", r"S\.?\s?Ct\.?", r"L\.?\s?Ed\.?(?:\s?(?:2d|3d|4th))?",
    r"F\.?\s?Supp\.?(?:\s?(?:2d|3d))?", r"F\.?\s?App(?:'|’)?x\.?",
    r"F\.?\s?(?:2d|3d|4th)", r"F\.", r"N\.?\s?Y\.?(?:\s?S\.?)?(?:\s?2d)?",
    r"N\.?\s?E\.?(?:\s?2d)?", r"N\.?\s?W\.?(?:\s?2d)?", r"S\.?\s?E\.?(?:\s?2d)?",
    r"S\.?\s?W\.?(?:\s?2d)?", r"So\.(?:\s?2d)?", r"A\.(?:\s?2d)?", r"P\.(?:\s?2d)?",
    r"Cal\.?\s?Rptr\.?", r"B\.?\s?R\.", r"WL",
]
REPORTER_CITE_RE = re.compile(
    rf"(?<![\w.])(\d{{1,4}})\s+({'|'.join(REPORTERS)})\s+(?:at\s+)?(\d{{1,6}})(?![\d])"
)
PUBLIC_CITE_RE = re.compile(
    rf"(?<!\d)(1[8-9]\d\d|20\d\d)\s+([A-Z]{{2}}(?:\s+App\.?)?)\s+(?:\(\d+(?:st|nd|rd|th)\)\s+)?(\d{{3,7}})(?:-[A-Z])?(?!\d)"
)

# Case name patterns
V = r"(?:v|vs|versus)\.?"
CORPORATE = {"co", "inc", "corp", "ltd", "llc", "company", "corporation", "railroad", "railway", "rr", "r.r"}
GENERIC_FIRST_WORDS = {"new", "united", "the", "state", "people", "city", "county", "commonwealth", "in", "ex"}
PARTY = r"[A-Z][\w.&'’-]*(?:\s+(?:of|the|and|for|de|la|du|ex\s+rel\.|&|[A-Z][\w.&'’-]*))*"
GENERIC_CASE_RE = re.compile(
    rf"\b({PARTY})\s+{V}\s+({PARTY})|\b(?:In\s+re|Ex\s+parte)\s+[A-Z][\w.&'’-]*(?:\s+[A-Z][\w.&'’-]*)*"
)
LEADING_SIGNALS = re.compile(
    r"^(?:(?:In|Under|See|As|Per|Cf\.?|But|And|Also|Compare|Following|Unlike|Like|Citing|Accord)\s+)+"
)

# Constitutional / Public-law claims
AMENDMENT_NUMS = r"(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|Eleventh|Twelfth|Thirteenth|Fourteenth|Fifteenth|1st|2nd|3rd|4th|5th|6th|7th|8th|9th|10th|14th)"
PUBLIC_LAW_RE = re.compile(
    rf"\b(?:The\s+)?({AMENDMENT_NUMS}\s+Amendment|Equal\s+Protection\s+Clause|Due\s+Process\s+Clause|Commerce\s+Clause|Establishment\s+Clause)\b",
    re.I,
)

HOLDING_SIGNALS = re.compile(
    r"\b(?:held\s+that|holds\s+that|holding\s+that|ruled\s+that|rules\s+that|"
    r"established\s+(?:that\s+)?|stands\s+for\s+(?:the\s+proposition\s+that\s+)?|"
    r"concluded\s+that|requires\s+|prohibits\s+|allows\s+|permits\s+|applies\s+|"
    r"excludes\s+|protects\s+|guarantees\s+|mandates\s+|bars\s+)",
    re.I,
)


def load_known_lists() -> tuple[list[dict], list[dict]]:
    """Load trusted and known fabricated case lists if present."""
    trusted, fabricated = [], []
    t_file = PARALEGAL_DIR / "trusted_citations.json"
    if t_file.exists():
        trusted = json.loads(t_file.read_text()).get("cases", [])
    f_file = PARALEGAL_DIR / "known_fabricated.json"
    if f_file.exists():
        fabricated = json.loads(f_file.read_text()).get("cases", [])
    return trusted, fabricated


def detect_prompt_injection(text: str) -> bool:
    """Check if memo contains instruction-shaped injection text."""
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def verify_quote(quote: str, full_text: str) -> tuple[bool, int, int]:
    """Verify that quote exists verbatim in full_text and return (valid, start, end)."""
    if not quote or not quote.strip():
        return False, -1, -1

    idx = full_text.find(quote)
    if idx != -1:
        return True, idx, idx + len(quote)

    compact_quote = re.sub(r"\s+", " ", quote).strip()
    compact_text = re.sub(r"\s+", " ", full_text)
    c_idx = compact_text.find(compact_quote)
    if c_idx != -1:
        words = compact_quote.split()
        if words:
            first_w, last_w = re.escape(words[0]), re.escape(words[-1])
            pattern = re.compile(rf"{first_w}.*?{last_w}", re.S)
            for m in pattern.finditer(full_text):
                candidate = m.group()
                if re.sub(r"\s+", " ", candidate).strip() == compact_quote:
                    return True, m.start(), m.end()

    return False, -1, -1


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Split text into sentence spans, ignoring periods in legal abbreviations."""
    spans, start = [], 0
    for m in re.finditer(r"[.!?;]+[\"'’”)\]]*(?=\s|$)", text):
        if m.group()[0] == ".":
            before = re.search(r"([A-Za-z.'’]+)$", text[start:m.start()])
            token = before.group(1).lower().replace("'", "").replace("’", "") if before else ""
            nxt = text[m.end():].lstrip()[:1]
            if token and (token.rstrip(".") in ABBREVIATIONS or len(token) == 1 or "." in token) or (nxt and nxt.islower()):
                continue
        spans.append((start, m.end()))
        start = m.end()
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans


def extract_citation_and_year(passage: str) -> tuple[str | None, int | None]:
    """Extract reporter citation and year from a text passage."""
    citation = None
    rep_match = REPORTER_CITE_RE.search(passage)
    if rep_match:
        citation = rep_match.group()
    else:
        pub_match = PUBLIC_CITE_RE.search(passage)
        if pub_match:
            citation = pub_match.group()

    year = None
    paren_year_match = PAREN_YEAR_RE.search(passage)
    if paren_year_match:
        year = int(paren_year_match.group(1))
    elif citation:
        after_cite = passage[passage.find(citation) + len(citation):]
        after_year = YEAR_RE.search(after_cite[:40])
        if after_year:
            year = int(after_year.group(1))
    else:
        y_match = YEAR_RE.search(passage)
        if y_match:
            year = int(y_match.group(1))

    return citation, year


def extract_holding_text(passage: str, case_name: str | None, citation: str | None) -> str:
    """Extract the legal proposition asserted in the passage."""
    t = passage
    if case_name:
        t = t.replace(case_name, " ")
    if citation:
        t = t.replace(citation, " ")

    t = PAREN_YEAR_RE.sub(" ", t)

    sig_match = HOLDING_SIGNALS.search(t)
    if sig_match:
        holding_candidate = t[sig_match.start():].strip(" ,;:")
        return re.sub(r"\s+", " ", holding_candidate)

    clean = re.sub(r"^[,\s;:-]+", "", t).strip(" ,;:")
    return re.sub(r"\s+", " ", clean)


def find_all_case_mentions(text: str, trusted: list[dict], fabricated: list[dict]) -> list[tuple[int, int, str]]:
    """Find all case mentions in text: full names, generic cases, and short names."""
    mentions = []

    def overlaps(s, e):
        return any(ms < e and s < me for ms, me, _ in mentions)

    # 1. Exact trusted and fabricated full names
    all_entries = [(e["case"], "full") for e in trusted + fabricated]
    for case_name, _ in sorted(all_entries, key=lambda x: len(x[0]), reverse=True):
        pattern = re.compile(rf"\b{re.escape(case_name)}\b", re.I)
        for m in pattern.finditer(text):
            if not overlaps(m.start(), m.end()):
                mentions.append((m.start(), m.end(), m.group()))

    # 2. Generic Party v. Party pattern
    for m in GENERIC_CASE_RE.finditer(text):
        written = LEADING_SIGNALS.sub("", m.group()).strip()
        start = m.end() - len(written)
        if not overlaps(start, m.end()):
            mentions.append((start, m.end(), written))

    # 3. Known short names
    for e in trusted + fabricated:
        first_party = re.split(rf"\s+{V}\s+", e["case"], maxsplit=1)[0].split()
        if first_party:
            short_name = first_party[0]
            if len(short_name) > 3 and short_name.lower() not in GENERIC_FIRST_WORDS:
                pattern = re.compile(rf"\b{re.escape(short_name)}\b", re.I)
                for m in pattern.finditer(text):
                    if not overlaps(m.start(), m.end()):
                        mentions.append((m.start(), m.end(), m.group()))

    return sorted(mentions, key=lambda x: x[0])


def extract_claims(text: str) -> list[Claim]:
    """Extract claims from text with precise word-for-word quotes."""
    trusted, fabricated = load_known_lists()
    mentions = find_all_case_mentions(text, trusted, fabricated)
    s_spans = sentence_spans(text)

    claims = []

    # Map mentions into sentence chunks
    for s_start, s_end in s_spans:
        s_text = text[s_start:s_end].strip()
        if not s_text:
            continue

        s_mentions = [m for m in mentions if s_start <= m[0] < s_end]

        # Filter out short name mentions if full case name for the same case exists in this sentence
        if len(s_mentions) > 1:
            full_cases = [m[2].lower() for m in s_mentions if " v" in m[2].lower() or " vs" in m[2].lower()]
            filtered_mentions = []
            for m in s_mentions:
                m_name_low = m[2].lower()
                # If this is a single-word short name and any full case begins with it, skip the short name
                if " v" not in m_name_low and any(fc.startswith(m_name_low) for fc in full_cases):
                    continue
                filtered_mentions.append(m)
            s_mentions = filtered_mentions

        if not s_mentions:
            # Check for pure public law claim
            pl_match = PUBLIC_LAW_RE.search(s_text)
            if pl_match and HOLDING_SIGNALS.search(s_text):
                holding = re.sub(r"\s+", " ", s_text).strip(" ,;:")
                # Quote is the exact sentence
                q_start = s_start + text[s_start:s_end].find(s_text)
                q_end = q_start + len(s_text)
                claims.append(Claim(
                    case_name=None,
                    citation=None,
                    year=None,
                    holding=holding,
                    quote=text[q_start:q_end],
                    start=q_start,
                    end=q_end,
                    is_public_law=True,
                ))
            continue

        # One or more case mentions in this sentence
        if len(s_mentions) == 1:
            m_start, m_end, m_name = s_mentions[0]
            citation, year = extract_citation_and_year(s_text)
            holding = extract_holding_text(s_text, m_name, citation)
            q_start = s_start + text[s_start:s_end].find(s_text)
            q_end = q_start + len(s_text)
            claims.append(Claim(
                case_name=m_name,
                citation=citation,
                year=year,
                holding=holding,
                quote=text[q_start:q_end],
                start=q_start,
                end=q_end,
                is_public_law=False,
            ))
        else:
            # Multiple mentions in one sentence (e.g. "Marbury ... and Mapp ...")
            # Divide sentence between mentions
            for i, m in enumerate(s_mentions):
                m_start, m_end, m_name = m
                chunk_start = s_start if i == 0 else m_start
                chunk_end = s_mentions[i + 1][0] if i + 1 < len(s_mentions) else s_end

                chunk_text = text[chunk_start:chunk_end].strip(" ,;:\n")
                if not chunk_text:
                    continue

                # Find exact slice in text
                offset_in_raw = text[chunk_start:chunk_end].find(chunk_text)
                q_start = chunk_start + offset_in_raw
                q_end = q_start + len(chunk_text)

                citation, year = extract_citation_and_year(chunk_text)
                holding = extract_holding_text(chunk_text, m_name, citation)
                claims.append(Claim(
                    case_name=m_name,
                    citation=citation,
                    year=year,
                    holding=holding,
                    quote=text[q_start:q_end],
                    start=q_start,
                    end=q_end,
                    is_public_law=False,
                ))

    return claims


def split_claims(text: str, model: str | None = None) -> SplitResult:
    """Split a memo into verified claims.

    Guarantees:
    - Every claim's quote exists word-for-word in the memo text.
    - If a quote does not match memo[start:end], it is discarded.
    - Flags instruction-shaped injection text.
    """
    flagged_injection = detect_prompt_injection(text)
    raw_claims = extract_claims(text)

    # Strictly verify word-for-word quotes
    verified_claims = []
    for c in raw_claims:
        if 0 <= c.start < c.end <= len(text) and text[c.start:c.end] == c.quote:
            verified_claims.append(c)

    return SplitResult(
        claims=verified_claims,
        source="code_verified",
        flagged_injection=flagged_injection,
        error=None,
    )
