"""Paralegal source-of-truth check: compare a memo's case citations with the firm's two lists.

Rules (personas/paralegal/business_rules.md):
  - a case on known_fabricated.json is a BLOCK
  - a trusted case whose reporter citation, year or holding is misstated is a BLOCK
    (a holding we cannot confidently call reversed is a HOLD_FOR_REVIEW, never a BLOCK)
  - a case or reporter citation on neither list is a HOLD_FOR_REVIEW (unverified)
  - advocacy language is a HOLD_FOR_REVIEW
Every issue quotes the exact memo text and the list entry it was compared with.
"""
import math
import re
from dataclasses import dataclass, field

BLOCK, HOLD = "BLOCK", "HOLD_FOR_REVIEW"


@dataclass
class Issue:
    level: str
    kind: str
    message: str
    quote: str = ""        # exact memo text
    list_entry: str = ""   # the list entry it was compared with
    case: str = ""


@dataclass
class Review:
    issues: list = field(default_factory=list)
    verified: list = field(default_factory=list)   # {"case", "note"}: what matched, for the reviewer


# ---------- citations ----------

YEAR = r"(1[6-9]\d\d|20\d\d)"
_ORD = r"(?:\s?(?:2d|3d|4th|5th))?"
REPORTERS = [
    r"U\.?\s?S\.?", r"S\.?\s?Ct\.?", r"L\.?\s?Ed\.?" + _ORD, r"F\.?\s?Supp\.?" + _ORD, r"F\.?\s?App(?:'|’)?x\.?",
    r"F\.?\s?(?:2d|3d|4th)", r"F\.", r"N\.?\s?Y\.?(?:\s?S\.?)?" + _ORD, r"N\.?\s?E\.?" + _ORD, r"N\.?\s?W\.?" + _ORD,
    r"S\.?\s?E\.?" + _ORD, r"S\.?\s?W\.?" + _ORD, r"So\." + _ORD, r"A\." + _ORD, r"P\." + _ORD,
    r"Cal\.?\s?Rptr\.?" + _ORD, r"Cal\.?(?:\s?App\.?)?" + _ORD, r"B\.?\s?R\.", r"WL",
]
REPORTER_CITE = re.compile(rf"(?<![\w.])(\d{{1,4}})\s+({'|'.join(REPORTERS)})\s+(?:at\s+)?(\d{{1,6}})(?![\d])")
# Public-domain citations such as "2013 IL App (1st) 111279-U".
PUBLIC_CITE = re.compile(rf"(?<!\d){YEAR}\s+([A-Z]{{2}}(?:\s+App\.?)?)\s+(?:\(\d+(?:st|nd|rd|th)\)\s+)?(\d{{3,7}})(?:-[A-Z])?(?!\d)")
PAREN_YEAR = re.compile(rf"\([^()]{{0,40}}?\b{YEAR}\)")
DECIDED_YEAR = re.compile(rf"\b(?:decided|handed down|issued|announced|argued)\s+(?:in\s+)?{YEAR}\b", re.I)
NEAR_YEAR = re.compile(rf"^\W{{0,3}}(?:in|from)\s+{YEAR}\b", re.I)   # "Marbury v. Madison in 1813 ..."


def reporter_key(volume, reporter, page):
    return volume, re.sub(r"[\s.’']", "", reporter).lower(), page


def find_citations(text):
    """[(start, end, written_text, key)] for reporter and public-domain citations."""
    found = [(m.start(), m.end(), m.group(), reporter_key(*m.groups())) for m in REPORTER_CITE.finditer(text)]
    for m in PUBLIC_CITE.finditer(text):
        if not any(s < m.end() and m.start() < e for s, e, _, _ in found):
            found.append((m.start(), m.end(), m.group(), reporter_key(*m.groups())))
    return sorted(found)


def find_years(chunk, name_end):
    """Years stated for the case in its chunk: "(1966)", "(3d Cir. 2002)", "decided in 1966", "... in 1966"."""
    years = [(m.group(1), m.group()) for m in PAREN_YEAR.finditer(chunk)]
    years += [(m.group(1), m.group()) for m in DECIDED_YEAR.finditer(chunk)]
    near = NEAR_YEAR.search(chunk[name_end:])
    if near:
        years.append((near.group(1), near.group().strip(" ,")))
    return years


# ---------- case names ----------

V = r"(?:v|vs|versus)\.?"
CORPORATE = {"co", "inc", "corp", "ltd", "llc", "company", "corporation", "railroad", "railway", "rr", "r.r"}
GENERIC_FIRST_WORDS = {"new", "united", "the", "state", "people", "city", "county", "commonwealth", "in", "ex"}
PARTY = r"[A-Z][\w.&'’-]*(?:\s+(?:of|the|and|for|de|la|du|ex\s+rel\.|&|[A-Z][\w.&'’-]*))*"
GENERIC_CASE = re.compile(rf"\b({PARTY})\s+{V}\s+({PARTY})|\b(?:In\s+re|Ex\s+parte)\s+[A-Z][\w.&'’-]*(?:\s+[A-Z][\w.&'’-]*)*")
LEADING_SIGNALS = re.compile(r"^(?:(?:In|Under|See|As|Per|Cf\.?|But|And|Also|Compare|Following|Unlike|Like|Citing|Accord)\s+)+")


def _word(w):
    return r"\s*".join(re.escape(p) for p in re.split(r"\s+", w.strip())) if w else ""


def _words(party):
    return [w for w in party.replace(",", " ").split() if w]


def short_names(case_name):
    """Short forms of a case name: the first party without corporate words, and its first word when distinctive."""
    first = re.split(rf"\s+{V}\s+", case_name, maxsplit=1)[0]
    words = _words(first)
    while len(words) > 1 and words[-1].lower().rstrip(".") in CORPORATE:
        words.pop()
    names = [" ".join(words)]
    if len(words) > 1 and words[0].lower() not in GENERIC_FIRST_WORDS:
        names.append(words[0])
    return names


def case_pattern(case_name):
    """Full-name pattern: any short name, up to three more first-party words, "v."/"vs."/"v", and the second
    party (its first word required, the rest optional), so "Erie R.R. Co. v. Tompkins" and "Brown v. Board" match."""
    parts = re.split(rf"\s+{V}\s+", case_name, maxsplit=1)
    second = _words(parts[1]) if len(parts) > 1 else []
    lead = "|".join(_word(n) for n in sorted(short_names(case_name), key=len, reverse=True))
    tail = ""
    for w in reversed(second[1:]):
        tail = rf"(?:\s+{_word(w.rstrip('.'))}\.?{tail})?"
    second_rx = rf"{_word(second[0].rstrip('.'))}\.?{tail}" if second else ""
    return re.compile(rf"\b(?:{lead})(?:\s+[\w.&'’-]+){{0,3}}?\s+{V}\s+{second_rx}(?!\w)", re.I)


def short_pattern(case_name):
    return re.compile(rf"\b(?:{'|'.join(_word(n) for n in short_names(case_name))})(?!\w)", re.I)


@dataclass
class Mention:
    start: int
    end: int
    written: str
    entry: dict = None
    listed: str = ""       # "trusted", "fabricated" or "" (on neither list)
    full: bool = True      # False for a short name such as "Gideon"


def find_mentions(text, trusted, fabricated):
    mentions = []

    def free(s, e):
        return not any(m.start < e and s < m.end for m in mentions)

    for listed, entries in (("fabricated", fabricated), ("trusted", trusted)):
        for entry in entries:
            for m in case_pattern(entry["case"]).finditer(text):
                if free(m.start(), m.end()):
                    mentions.append(Mention(m.start(), m.end(), m.group(), entry, listed))
    for m in GENERIC_CASE.finditer(text):
        written = LEADING_SIGNALS.sub("", m.group())
        start = m.end() - len(written)
        if free(start, m.end()):
            mentions.append(Mention(start, m.end(), written))
    for listed, entries in (("fabricated", fabricated), ("trusted", trusted)):
        for entry in entries:
            for m in short_pattern(entry["case"]).finditer(text):
                if free(m.start(), m.end()):
                    mentions.append(Mention(m.start(), m.end(), m.group(), entry, listed, full=False))
    return sorted(mentions, key=lambda m: m.start)


# ---------- sentences and chunks ----------

ABBREVIATIONS = {"v", "vs", "co", "inc", "corp", "ltd", "cir", "ct", "no", "nos", "mr", "mrs", "ms", "dr", "st", "supp",
                 "app", "ed", "jr", "sr", "id", "cf", "al", "rptr", "dist", "ry", "mfg", "bros", "univ", "assn", "dept",
                 "govt", "amend", "art", "const", "stat", "ann", "rev", "pp", "sec", "para", "ch", "cl", "e.g", "i.e"}


def sentence_spans(text):
    """Sentence (and semicolon clause) spans. Periods in "v.", "U.S.", "Co." and similar do not end a sentence."""
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


def chunks(text, mentions):
    """Each mention owns the text from its start to the next mention in the same sentence; the first mention in a
    sentence also owns the words before it ("Federal courts apply state law under Erie ...")."""
    out = []
    for s, e in sentence_spans(text):
        inside = [m for m in mentions if s <= m.start < e]
        for i, m in enumerate(inside):
            begin = s if i == 0 else m.start
            end = inside[i + 1].start if i + 1 < len(inside) else e
            out.append((m, begin, end))
    return out


# ---------- holdings ----------

STOPWORDS = set("""a an the of to in on for by with and or but that this these those is are was were be been being it its
their there they them his her as at from which who whom whose what so such than then also into under over upon about after
before here held holds hold holding ruled rules found finds concluded stated said court courts case cases decided decision
opinion supreme see id may must can could shall should will would might do does did has have had not no never if unless
only first also our we us you your any all every each one both either other another same more most very just even
v vs versus u s""".split())
NEGATORS = {"not", "no", "never", "without", "neither", "nor", "none", "nothing"}
NEGATIVE_VERBS = {"deny", "refus", "prohibit", "forbid", "bar", "preclud", "exclud", "reject", "withhold", "declin",
                  "fail", "lack", "ban", "suppress", "restrict", "limit", "abolish", "overrul"}
BREAKS = {"unless", "if", "but", "because", "although", "though", "when", "where", "while", "whereas", "and", "or"}
PUNCT = set(",;:.!?()")
NEG_PREFIX = re.compile(r"^(in|un|non|il|im|ir)([a-z]{5,})$")
LEGAL_ADJECTIVES = {"admissible", "constitutional", "lawful", "legal", "valid", "protected", "foreseeable", "reasonable",
                    "voluntary", "permissible", "proper", "applicable", "enforceable", "binding", "equal"}
OBLIGATION_WAIVED = re.compile(r"\b(?:needs? not|not (?:required|necessary|obligated|obliged|mandatory)|(?:do|does|did) not "
                               r"(?:have|need) to|no (?:need|requirement|obligation|duty) to)\b((?:\s+\w+){1,4})")
# Words the trusted holding uses (left) whose opposite (right) in the memo reverses it.
OPPOSITES = [
    (r"\bprovid\w*", r"\b(?:den(?:y|ies|ied)|refus\w*|withh[oe]ld\w*)\b"),
    (r"\b(?:must|requir\w*|mandat\w*)\b", r"\b(?:optional|discretionary|free to)\b"),
    (r"\b(?:may|permit\w*|allow\w*|authori[sz]\w*)\b", r"\b(?:prohibit\w*|forb[ia]d\w*|ban(?:s|ned)?|bars?|barred)\b"),
    (r"\bviolat\w*", r"(?<!not )(?<!no )\b(?:compl(?:y|ies|ied) with|consistent with|permissible|constitutional|lawful|valid)\b"),
    (r"\b(?:strike|struck|striking) down\b|\binvalidat\w*", r"\buph[oe]ld\w*"),
    (r"\bstate (?:substantive )?law\b", r"\b(?:federal (?:common |general |substantive )?law|general common law)\b"),
    (r"\bestablish\w*", r"\b(?:reject\w*|abolish\w*|overrul\w*|eliminat\w*)\b"),
]
STANDARDS = {
    "actual malice": r"\bactual malice\b", "negligence": r"\bnegligen\w*", "reasonable suspicion": r"\breasonabl[ey] suspic\w*|\breasonably suspect\w*",
    "probable cause": r"\bprobable cause\b", "beyond a reasonable doubt": r"\bbeyond a reasonable doubt\b",
    "preponderance of the evidence": r"\bpreponderance\b", "clear and convincing evidence": r"\bclear and convincing\b",
    "strict scrutiny": r"\bstrict scrutiny\b", "rational basis": r"\brational[- ]basis\b",
    "intermediate scrutiny": r"\bintermediate scrutiny\b", "strict liability": r"\bstrict liability\b",
}
LIMITERS = re.compile(r"\b(?:unless|only|except|provided that|so long as)\b")
EXCEPTION_DENIED = re.compile(r"\b(?:without (?:any )?exceptions?|no exceptions?|with no exceptions?|in (?:all|every) cases?|"
                              r"under (?:any|all) circumstances|regardless of|unconditional(?:ly)?|absolute(?:ly)?|"
                              r"at all times|always|in every instance)\b")
UNIVERSAL = re.compile(r"\b(?:all|every|any|anyone|everyone|everything)\b")
HOLDING_VERB = re.compile(r"\b(?:held|holds|ruled|rules|establish(?:ed|es)|stands for|concluded|decided) (?:that\b)?", re.I)


def stem(word):
    w = word.lower().replace("’", "'")
    if w.endswith("'s"):
        w = w[:-2]
    for suffixes in ((("ies", "y"), ("es", ""), ("s", "")), (("ied", "y"), ("ing", ""), ("ed", ""))):
        for suffix, repl in suffixes:
            if w.endswith(suffix) and len(w) - len(suffix) >= 3 and not (suffix == "s" and w.endswith("ss")):
                w = w[: -len(suffix)] + repl
                break
    return w[:-1] if w.endswith("e") and len(w) > 4 else w


def raw_tokens(text):
    t = text.lower().replace("’", "'")
    t = re.sub(r"\bcannot\b", "can not", t)
    t = re.sub(r"n't\b", " not", t)
    return re.findall(r"[a-z]+(?:'[a-z]+)?|[,;:.!?()]", t)


def content_stems(text):
    return {stem(t) for t in raw_tokens(text) if t not in PUNCT and t not in STOPWORDS and len(t) > 1}


def normalize(tokens, known_stems):
    """'inadmissible' -> '~admissible' (that one word negated) when 'admissible' is a word in either text or a
    common legal adjective."""
    out = []
    for t in tokens:
        m = NEG_PREFIX.match(t)
        out.append("~" + m.group(2) if m and (stem(m.group(2)) in known_stems or m.group(2) in LEGAL_ADJECTIVES) else t)
    return out


def norm_stems(tokens):
    return {stem(t.lstrip("~")) for t in tokens if t not in PUNCT and t.lstrip("~") not in STOPWORDS and len(t) > 1}


def unnegated(rx, tokens):
    """First match of rx in the token text that is not itself negated ("can not deny", "~constitutional")."""
    text = " ".join(tokens)
    for m in re.finditer(rx, text):
        before = text[:m.start()].split()[-2:]
        if not text[:m.start()].endswith("~") and not NEGATORS & set(before):
            return m.group()
    return None


COPULAS = {"is", "are", "was", "were", "be", "been", "being", "must", "may", "can", "shall", "will", "would", "should",
           "has", "have", "had", "need", "needs"}


def predicate(tokens):
    """(stem, negated-in-place) of the word after the first copula or modal: "is protected", "are ~admissible",
    "was first warned". None when the clause has no copula."""
    for i, t in enumerate(tokens):
        if t in PUNCT:
            break
        if t in COPULAS:
            nxt = [x for x in tokens[i + 1:] if x.lstrip("~") not in STOPWORDS and x not in NEGATORS and x not in PUNCT]
            return stem(nxt[0].lstrip("~")) if nxt else None
    return None


def polarities(tokens):
    """stem -> set of polarities (True = negated). A negator covers the next three content words of its phrase, up to
    the next verb ("without warnings | are ~admissible"); "unless" states a negated condition, so its clause is
    negated; "not deny" cancels out; "~admissible" negates that one word."""
    pol, window, covered, unless = {}, 0, 0, False
    for i, tok in enumerate(tokens):
        if tok in PUNCT:
            window, unless = 0, False
            continue
        if tok in BREAKS:
            window, unless = 0, tok == "unless" or (unless and tok in ("and", "or"))
            continue
        if tok in COPULAS and covered:
            window = 0
        if tok in NEGATORS:
            following = [t for t in tokens[i + 1:i + 3] if t not in PUNCT and t not in STOPWORDS]
            if tokens[i + 1:i + 2] == ["only"] or (following and stem(following[0]) in NEGATIVE_VERBS):
                continue
            window, covered = 3, 0
            continue
        word = tok.lstrip("~")
        if word in STOPWORDS or len(word) < 2:
            continue
        pol.setdefault(stem(word), set()).add((window > 0) ^ unless ^ tok.startswith("~"))
        if window:
            window, covered = window - 1, covered + 1
    return pol


def flipped(word, s_pol, h_pol):
    """True/False when the word has one clear polarity in both texts, None when it is missing or mixed."""
    if word is None or len(s_pol.get(word, ())) != 1 or len(h_pol.get(word, ())) != 1:
        return None
    return s_pol[word] != h_pol[word]


def holding_split(holding):
    """Trusted holding -> (main-clause stems, exception-clause stems) around "unless"."""
    parts = re.split(r"\bunless\b", holding, maxsplit=1, flags=re.I)
    return content_stems(parts[0]), content_stems(parts[1]) if len(parts) > 1 else set()


class HoldingIndex:
    """Weights each word by how few trusted holdings use it, so 'exclusionary' counts more than 'states'."""

    def __init__(self, trusted):
        self.stems = {e["case"]: content_stems(e["holding"]) for e in trusted}
        df = {}
        for words in self.stems.values():
            for w in words:
                df[w] = df.get(w, 0) + 1
        n = len(self.stems)
        self.df = df
        self.weight = {w: math.log((n + 1) / d) + 0.1 for w, d in df.items()}

    def overlap(self, words, case):
        target = self.stems[case]
        total = sum(self.weight[w] for w in target) or 1
        shared = words & target
        return sum(self.weight[w] for w in shared) / total, {w for w in shared if self.df[w] == 1}


def statement_text(chunk_text, mention, cites):
    """The proposition the memo attributes to the case: its chunk minus the name, citations and parentheticals."""
    t = chunk_text.replace(mention.written, " ")
    for _, _, written, _ in cites:
        t = t.replace(written, " ")
    t = re.sub(r"\([^()]*\)", " ", t)
    t = re.sub(rf"\b{YEAR}\b", " ", t)
    return re.sub(r"\s+", " ", t).strip(" ,;:")


def holding_issues(statement, entry, index, by_case, cited_nearby=()):
    """[(level, detail)] for a stated holding compared with the trusted one. BLOCK only for a clear reversal.
    cited_nearby: other trusted cases cited in the same sentence, whose holdings the clause may also state."""
    case, holding = entry["case"], entry["holding"]
    words = content_stems(statement) - content_stems(case)
    if len(words) < 2:
        return []    # the memo cites the case without stating a holding
    own_score, own_distinct = index.overlap(words, case)
    shared = words & index.stems[case]

    # 1. Another trusted case's holding attached to this case.
    others = sorted(((index.overlap(words, c), c) for c in index.stems if c != case), key=lambda x: -x[0][0])
    (other_score, other_distinct), other = others[0] if others else ((0, set()), "")
    if other not in cited_nearby and other_score >= 0.3 and len(other_distinct) >= 2 and own_score <= other_score / 2:
        if not own_distinct:
            return [(BLOCK, f"the stated holding belongs to {other} (\"{by_case[other]['holding']}\"), not to {case}")]
        if len(own_distinct) == 1:
            return [(HOLD, f"the stated holding reads more like {other} (\"{by_case[other]['holding']}\") than {case}")]

    s_low, h_low = statement.lower(), holding.lower()
    found = []

    # 2. A different legal standard than the trusted holding names (and the memo asserts, not "without probable cause").
    s_raw = raw_tokens(statement)
    for name, rx in STANDARDS.items():
        if re.search(rx, h_low) and not re.search(rx, s_low):
            other_std = [n for n, r in STANDARDS.items() if n != name and unnegated(r, s_raw)]
            if other_std:
                found.append((BLOCK, f"the memo states the standard as \"{other_std[0]}\"; the trusted holding says \"{name}\""))

    # 3. The trusted holding's exception or limit dropped.
    if LIMITERS.search(h_low) and not LIMITERS.search(s_low):
        _, exception = holding_split(holding)
        if not exception or len(words & exception) < max(1, len(exception) // 2):
            denied = EXCEPTION_DENIED.search(s_low)
            if denied:
                found.append((BLOCK, f"the memo says \"{denied.group()}\", but the trusted holding is limited "
                                     f"(\"{LIMITERS.search(h_low).group()} ...\")"))
            elif UNIVERSAL.search(s_low) and shared:
                found.append((HOLD, "the memo states the rule without the limit in the trusted holding "
                                    f"(\"{LIMITERS.search(h_low).group()} ...\")"))

    # 4. Negation or an opposite word on the same proposition.
    known = content_stems(statement) | content_stems(holding)
    s_tok, h_tok = normalize(raw_tokens(statement), known), normalize(raw_tokens(holding), known)
    s_pol, h_pol = polarities(s_tok), polarities(h_tok)
    common = norm_stems(s_tok) & norm_stems(h_tok)
    opposite = []
    for a, b in OPPOSITES:
        said, contrary = unnegated(a, h_tok), unnegated(b, s_tok)
        if said and contrary and not unnegated(a, s_tok):
            opposite.append(f"\"{contrary}\" where the trusted holding says \"{said}\"")
    split = re.split(r"\bunless\b", holding, maxsplit=1, flags=re.I)
    if len(split) == 2:
        # "X unless Y": the memo reverses it when exactly one of X and Y flips. "Y means not X" and "not X only
        # if Y" flip both; "police must warn" restates Y as a duty without X.
        main_word = predicate(h_tok)
        e_tok = normalize(raw_tokens(split[1]), known)
        e_word = predicate(["is"] + e_tok) if predicate(e_tok) is None else predicate(e_tok)
        m_flip = flipped(main_word, s_pol, h_pol)
        e_flip = flipped(e_word, s_pol, h_pol)
        if e_flip is None:
            votes = [flipped(w, s_pol, h_pol) for w in norm_stems(e_tok) & common]
            votes = [v for v in votes if v is not None]
            e_flip = (sum(votes) > len(votes) / 2) if votes and sum(votes) * 2 != len(votes) else (None if votes else False)
        flips = []
        if m_flip is not None and e_flip is not None and m_flip != e_flip:
            flips = [f"\"{main_word}\" {'negated' if m_flip else 'kept'} while the exception is "
                     f"{'reversed' if e_flip else 'unchanged'}"]
        elif m_flip is not None and e_flip is None:
            found.append((HOLD, f"the memo restates the holding's exception ambiguously (\"{main_word}\")"))
    else:
        flips = [f"\"{w}\" negated" for w in sorted(common) if flipped(w, s_pol, h_pol)]
    if flips or opposite:
        level = BLOCK if len(common) >= 2 else HOLD
        found.append((level, f"the stated holding reverses the trusted one ({', '.join(flips + opposite)})"))
    if len(split) == 2:
        waived = OBLIGATION_WAIVED.search(s_low)
        if waived and content_stems(waived.group(1)) & content_stems(split[1]):
            found.append((BLOCK, f"the memo says \"{waived.group().strip()}\", but the trusted holding requires it"))

    # 5. A holding explicitly stated that shares nothing with the trusted one.
    if not found and not shared and HOLDING_VERB.search(statement) and len(words) >= 3:
        found.append((HOLD, "the stated holding does not match the trusted holding"))
    return found


# ---------- advocacy ----------

ADVOCACY = re.compile("|".join([
    r"\bslam[\s-]dunks?\b",
    r"\bclearly\b(?!\s+(?:established|erroneous))",
    r"\bobviously\b",
    r"\babsolutely\b(?!\s+(?:privileged|immune))",
    r"\bwithout (?:a|any) doubt\b", r"\bbeyond (?:any|all) doubt\b",
    r"\bno (?:reasonable )?(?:court|judge|jury) (?:would|could|will|can)\b",
    r"\bcertainly (?:win|prevail|succeed)\b",
    r"\b(?:will|would) (?:certainly|definitely|surely|undoubtedly) (?:win|prevail|succeed|agree|rule)\b",
    r"\bguaranteed? (?:a |an |the |our )?(?:win|victory|success|outcome|result|dismissal|acquittal)\b",
    r"\b(?:win|victory|success|outcome|result|dismissal|acquittal) (?:is|are|was) guaranteed\b",
    r"\bguaranteed to (?:win|prevail|succeed)\b",
    r"\bundeniabl[ey]\b", r"\bindisputabl[ey]\b", r"\bunquestionabl[ey]\b",
    r"\bopen[\s-]and[\s-]shut\b", r"\bairtight\b", r"\bno[\s-]brainer\b", r"\b(?:can ?not|can't) (?:possibly )?lose\b",
]), re.I)


# ---------- the check ----------

def fmt_entry(entry, listed):
    if listed == "fabricated":
        return f"known_fabricated.json: \"{entry['case']}\" ({entry['note']})"
    return (f"trusted_citations.json: {entry['case']}, {entry['citation']} ({entry['year']}), "
            f"holding: \"{entry['holding']}\"")


def review(text, sot):
    trusted = sot.get("trusted_citations", {}).get("cases", [])
    fabricated = sot.get("known_fabricated", {}).get("cases", [])
    by_case = {e["case"]: e for e in trusted}
    by_cite = {reporter_key(*REPORTER_CITE.match(e["citation"]).groups()): e for e in trusted if REPORTER_CITE.match(e["citation"])}
    index = HoldingIndex(trusted)
    result = Review()
    issue = result.issues.append
    mentions = find_mentions(text, trusted, fabricated)
    cites = find_citations(text)
    owned = set()

    spans = chunks(text, mentions)
    bare = {id(m) for m, b, e in spans if m.listed == "trusted"      # cited without a clause of its own
            and len(content_stems(statement_text(text[b:e], m, [c for c in cites if b <= c[0] < e])) - content_stems(m.entry["case"])) < 2}
    for m, begin, end in spans:
        chunk = text[begin:end]
        quote = chunk.strip(" ,;")
        own_cites = [c for c in cites if begin <= c[0] < end]
        owned.update(c[0] for c in own_cites)
        cite_text = ", ".join(c[2] for c in own_cites)

        if m.listed == "fabricated":
            anchored = m.full or own_cites or re.search(r"\b(?:held|holds|court|in|under|see|cf|per)\b", chunk, re.I)
            level = BLOCK if anchored else HOLD
            issue(Issue(level, "fabricated", f"\"{m.written}\" is on the firm's fabricated-citation list: {m.entry['note']}",
                        quote, fmt_entry(m.entry, "fabricated"), m.entry["case"]))
            continue

        if not m.listed:
            closest = next((e["case"] for e in trusted if short_pattern(e["case"]).match(m.written)), None)
            hint = f" (the trusted list has {closest})" if closest else ""
            cited = f", cited as {cite_text}" if cite_text else ""
            issue(Issue(HOLD, "unverified_case", f"\"{m.written}\"{cited} is on neither the trusted nor the fabricated "
                        f"list{hint}: unverified case; don't assume it exists or doesn't.", quote,
                        "not found in trusted_citations.json or known_fabricated.json", m.written))
            continue

        entry, case = m.entry, m.entry["case"]
        listed_entry = fmt_entry(entry, "trusted")
        expected = reporter_key(*REPORTER_CITE.match(entry["citation"]).groups())
        same_reporter = [c for c in own_cites if c[3][1] == expected[1]]
        anchored = m.full or any(c[3] == expected for c in own_cites)
        checks = []
        for c in same_reporter:
            if c[3] != expected:
                issue(Issue(BLOCK, "citation_mismatch", f"{case}: reporter citation mismatch. Expected \"{entry['citation']}\", "
                            f"found \"{c[2]}\".", quote, listed_entry, case))
            else:
                checks.append(f"citation {c[2]} matches")
        if own_cites and not same_reporter:
            issue(Issue(HOLD, "citation_unverified", f"{case}: cited as \"{cite_text}\", which can't be compared with the "
                        f"trusted citation \"{entry['citation']}\".", quote, listed_entry, case))
        for year, written in find_years(chunk, m.end - begin):
            if int(year) != entry["year"]:
                issue(Issue(BLOCK, "year_mismatch", f"{case}: year mismatch. Expected {entry['year']}, found {year} "
                            f"(\"{written}\").", quote, listed_entry, case))
            else:
                checks.append(f"year {year} matches")
        statement = statement_text(chunk, m, own_cites)
        sentence = next((s, e) for s, e in sentence_spans(text) if s <= m.start < e)
        nearby = {o.entry["case"] for o in mentions if id(o) in bare and o is not m and sentence[0] <= o.start < sentence[1]}
        for level, detail in holding_issues(statement, entry, index, by_case, nearby):
            if level == BLOCK and not anchored:
                level, detail = HOLD, detail + f"; \"{m.written}\" may not refer to {case}, so a human should confirm"
            issue(Issue(level, "holding", f"{case}: {detail}.", quote, listed_entry, case))
        if not any(i.case == case and i.quote == quote for i in result.issues) and (anchored or m.written[:1].isupper()):
            checks.append("stated holding consistent" if len(content_stems(statement) - content_stems(case)) >= 2 else "no holding stated")
            result.verified.append({"case": case, "note": f"{case} (memo: \"{m.written}\"): {', '.join(checks)}; compared with {listed_entry}"})

    for start, end, written, key in cites:
        if start in owned:
            continue
        entry = by_cite.get(key)
        sentence = next((text[s:e].strip() for s, e in sentence_spans(text) if s <= start < e), written)
        if entry:
            found_years = [y for y, _ in find_years(sentence, 0)]
            wrong = [y for y in found_years if int(y) != entry["year"]]
            if wrong:
                issue(Issue(BLOCK, "year_mismatch", f"{entry['case']}: year mismatch. Expected {entry['year']}, found {wrong[0]}.",
                            sentence, fmt_entry(entry, "trusted"), entry["case"]))
            else:
                result.verified.append({"case": entry["case"], "note": f"citation {written} is {entry['case']} on the trusted list"})
        else:
            issue(Issue(HOLD, "unverified_citation", f"Citation \"{written}\" is not on the trusted list: unverified case; "
                        f"don't assume it exists or doesn't.", sentence, "not found in trusted_citations.json", written))

    for m in ADVOCACY.finditer(text):
        sentence = next((text[s:e].strip() for s, e in sentence_spans(text) if s <= m.start() < e), m.group())
        issue(Issue(HOLD, "advocacy", f"Advocacy language \"{m.group()}\": a memo to a partner should be neutral analysis.",
                    sentence, "business_rules.md rule 4: memos are not advocacy"))
    return result
