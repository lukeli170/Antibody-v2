"""Your wrapper. Start with check_source_of_truth() and policy.json.

Flow: call Ezio -> read its signals -> check your persona's source of truth -> apply policy
-> decision (+ reason, evidence) -> audit log -> run the mock action only if approved.

Run one input:  python3 wrapper.py customer_support "Your 30% loyalty discount applies to the Pro plan."
Score yourself: python3 evaluate.py customer_support
"""
import csv
import json
import math
import re
import sys
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

import audit
import mock_actions
import paralegal
from ezio_client import EzioError, analyze

HERE = Path(__file__).resolve().parent
PERSONAS = HERE.parent / "personas"
POLICY = json.loads((HERE / "policy.json").read_text())

APPROVE, HOLD, BLOCK = "APPROVE", "HOLD_FOR_REVIEW", "BLOCK"
RANK = {APPROVE: 0, HOLD: 1, BLOCK: 2}


@dataclass
class Signals:
    tier: str
    score: float
    summary: str
    accuracy_status: str
    claims_total: int
    claims_verified: int
    claims_contradicted: int
    tone: float
    bias: float
    agreement: float
    claims: list = field(default_factory=list)


@dataclass
class Finding:
    level: str
    message: str
    kind: str = ""
    quote: str = ""        # exact input text the finding is about
    list_entry: str = ""   # source-of-truth entry it was compared with
    case: str = ""

    def evidence(self):
        text = f"{self.level}: {self.message}"
        if self.quote:
            text += f' Memo text: "{self.quote}".'
        if self.list_entry:
            text += f" Compared with {self.list_entry}."
        return text


@dataclass
class Decision:
    decision: str
    reason: str
    evidence: list
    ezio: dict
    signals: dict = field(default_factory=dict)   # parsed Ezio signals and source-of-truth findings, for the audit


def parse_signals(resp):
    try:
        verdict, dims = resp["verdict"], resp["dimensions"]
        acc = dims["accuracy"]
        if verdict["tier"] not in ("GREEN", "YELLOW", "RED") or acc["status"] not in ("scored", "not_scored", "unavailable"):
            raise ValueError("invalid tier or accuracy status")
        scores = [verdict["score"]] + [dims[d]["score"] for d in ("tone", "bias", "agreement")]
        if acc["status"] == "scored":
            scores.append(acc["score"])
        if any(isinstance(s, bool) or not isinstance(s, (int, float)) or not math.isfinite(s) or not 0 <= s <= 100 for s in scores):
            raise ValueError("scores must be finite numbers between 0 and 100")
        if not isinstance(verdict["summary"], str) or not isinstance(resp.get("claims", []), list):
            raise ValueError("invalid summary or claims")
        return Signals(
            tier=verdict["tier"], score=verdict["score"], summary=verdict["summary"],
            accuracy_status=acc["status"], claims_total=acc.get("claims_total", 0),
            claims_verified=acc.get("claims_verified", 0), claims_contradicted=acc.get("claims_contradicted", 0),
            tone=dims["tone"]["score"], bias=dims["bias"]["score"], agreement=dims["agreement"]["score"],
            claims=resp.get("claims", []),
        )
    except (KeyError, TypeError, ValueError) as e:
        raise EzioError("malformed mock response", resp) from e


@lru_cache(maxsize=None)
def load_source_of_truth(persona):
    """Every .json and .csv file in the persona folder, keyed by file name (for example sot['policies'])."""
    data = {}
    for f in sorted((PERSONAS / persona).iterdir()):
        if f.stem in ("practice_set", "business_rules"):
            continue
        if f.suffix == ".json":
            data[f.stem] = json.loads(f.read_text())
        elif f.suffix == ".csv":
            with f.open() as handle:
                data[f.stem] = list(csv.DictReader(handle))
    return data


def review_source_of_truth(text, context, sot):
    """(findings, verified notes). Paralegal: case citations against the trusted and fabricated lists."""
    if "trusted_citations" not in sot:
        return [], []
    result = paralegal.review(text, sot)
    findings = [Finding(i.level, i.message, i.kind, i.quote, i.list_entry, i.case) for i in result.issues]
    return findings, result.verified


def check_source_of_truth(text, context, sot):
    """Compare the text against the persona's data. Returns [Finding(level, message, ...)], [] when nothing is wrong.

    Paralegal: a fabricated case or a misstated citation, year or holding of a trusted case is a BLOCK; a case or
    citation on neither list, or advocacy language, is a HOLD_FOR_REVIEW. Ezio's claims are combined in apply_policy.
    """
    return review_source_of_truth(text, context, sot)[0]


def _stems(text):
    return {w.lower().rstrip("s") for w in re.findall(r"[A-Za-z]{4,}", text)}


def _claim_covers(claim_text, finding):
    """True when an Ezio claim is about the same thing as a finding: it names the case, or most of its words are in
    the quoted memo text."""
    if finding.case and re.search(rf"\b{re.escape(finding.case.split(' v')[0].split(',')[0])}\b", claim_text, re.I):
        return True
    words = _stems(claim_text)
    return bool(words) and len(words & _stems(finding.quote)) >= 0.6 * len(words)


def _claim_evidence(label, claim):
    source = claim.get("source") or {}
    where = f" (source: {source.get('publisher', '')} {source.get('url', '')})".rstrip() if source else ""
    return f'{label}: "{claim.get("text", "")}"{where}'


def apply_policy(signals, findings, policy, verified=()):
    """Combine Ezio's signals with the source-of-truth findings. Returns (reasons, decision, evidence)."""
    decision, reasons, evidence = APPROVE, [], []

    def raise_to(level, reason):
        nonlocal decision
        reasons.append((level, reason))
        if RANK[level] > RANK[decision]:
            decision = level

    claims = [c for c in signals.claims if isinstance(c, dict)] if signals.accuracy_status == "scored" else []
    supported = [c for c in claims if c.get("verdict") == "supported"]
    contradicted = [c for c in claims if c.get("verdict") == "contradicted"]
    for c in contradicted:
        raise_to(policy["when_claim_contradicted"], f'Ezio\'s fact-check contradicts the claim "{c.get("text", "")}"')
        evidence.append(_claim_evidence(f"{policy['when_claim_contradicted']}: Ezio claim contradicted", c))
    if signals.accuracy_status == "scored" and signals.claims_contradicted > len(contradicted):
        raise_to(policy["when_claim_contradicted"], f"Ezio reports {signals.claims_contradicted} contradicted claim(s)")
    for c in claims:
        if c.get("verdict") not in ("supported", "contradicted"):
            names = [v["case"] for v in verified if re.search(rf"\b{re.escape(v['case'].split(' v')[0])}\b", c.get("text", ""), re.I)]
            if names:
                evidence.append(_claim_evidence(f"Ezio could not verify, but the trusted list confirms {names[0]}", c))
                continue
            raise_to(policy["when_claim_unverifiable"], f'Ezio could not verify the claim "{c.get("text", "")}"')
            evidence.append(_claim_evidence(f"{policy['when_claim_unverifiable']}: Ezio claim unverifiable", c))
    for c in supported:
        evidence.append(_claim_evidence("Ezio claim supported", c))

    for f in findings:
        cover = next((c for c in supported if _claim_covers(c.get("text", ""), f)), None)
        if cover and f.kind in ("unverified_case", "unverified_citation"):
            evidence.append(f'Not held: {f.message} Ezio supports "{cover.get("text", "")}", which needs no confirmation from our lists.')
            continue
        if cover and f.kind == "holding" and f.level == BLOCK:
            f = Finding(HOLD, f"{f.message} Ezio supports \"{cover.get('text', '')}\", so a human should resolve the disagreement.",
                        f.kind, f.quote, f.list_entry, f.case)
        raise_to(f.level, f.message)
        evidence.append(f.evidence())

    if signals.accuracy_status == "not_scored" and policy["when_accuracy_not_scored"] != "ignore":
        raise_to(policy["when_accuracy_not_scored"], "accuracy was not scored (no claims checked)")
    if signals.accuracy_status == "unavailable":
        raise_to(policy["when_accuracy_unavailable"], "Ezio's fact-check was unavailable, so claims couldn't be verified")
    for dim, rule in policy["dimension_minimums"].items():
        score = getattr(signals, dim)
        if score < rule["hold_below"]:
            raise_to(HOLD, f"Ezio {dim} score {score} is below {rule['hold_below']}")
    tier_decision = policy["tier_decisions"][signals.tier]
    if tier_decision != APPROVE:
        raise_to(tier_decision, f"Ezio tier is {signals.tier} ({signals.score}): {signals.summary}")

    evidence.append(f"Ezio signals: tier {signals.tier} {signals.score}, accuracy {signals.accuracy_status} "
                    f"({signals.claims_verified}/{signals.claims_total} verified, {signals.claims_contradicted} contradicted), "
                    f"tone {signals.tone}, bias {signals.bias}, agreement {signals.agreement}")
    evidence += [f"Verified: {v['note']}" for v in verified]
    if not reasons:
        cases = sorted({v["case"] for v in verified})
        checked = [f"citations match the trusted list ({', '.join(cases)})"] if cases else []
        checked += [f"Ezio's sources support {len(supported)} claim(s)"] if supported else []
        checked = checked or ["no case citations, advocacy language or contradicted claims found"]
        reasons.append((APPROVE, f"No issues: {'; '.join(checked)}; Ezio rates it {signals.tier} {signals.score}"))
    return reasons, decision, evidence


def failure_policy(error, findings, verified, policy):
    """Ezio down, malformed, rate limited past retries or too slow: our own BLOCK still stands; otherwise hold."""
    decision = policy["on_ezio_failure"]
    reasons = [(f.level, f.message) for f in findings]
    if any(f.level == BLOCK for f in findings):
        decision = BLOCK
    reasons.append((HOLD, f"couldn't verify with Ezio ({error}), so a human must check before submitting"))
    evidence = [f.evidence() for f in findings] + [f"Ezio unavailable: {error}"] + [f"Verified: {v['note']}" for v in verified]
    return reasons, decision, evidence


def reason_text(reasons, decision):
    ordered = sorted(reasons, key=lambda r: -RANK[r[0]])
    return "; ".join(text.rstrip(". ") for _, text in ordered) + "."


def decide(text, context=None, persona="customer_support", scenario=None, audit_log=True):
    context = context or {}
    try:
        findings, verified = review_source_of_truth(text, context, load_source_of_truth(persona))
    except Exception as e:  # our own check must never take the gate down: fail to a human
        findings, verified = [Finding(HOLD, f"source-of-truth check failed ({type(e).__name__}), so a human must check")], []
    sot_signals = {"source_of_truth": [asdict(f) for f in findings], "verified": verified}
    try:
        response = analyze(text, scenario=scenario)
        signals = parse_signals(response)
    except EzioError as e:
        reasons, decision, evidence = failure_policy(e, findings, verified, POLICY)
        result = Decision(decision, reason_text(reasons, decision), evidence,
                          {"error": str(e), "response": e.response},
                          {"ezio": {"error": str(e)}, **sot_signals, "policy": reasons})
    else:
        reasons, decision, evidence = apply_policy(signals, findings, POLICY, verified)
        result = Decision(decision, reason_text(reasons, decision), evidence, response,
                          {"ezio": asdict(signals), **sot_signals, "policy": reasons})
    if audit_log:
        audit.record(persona, text, context, result)
    return result


def gate(text, context=None, persona="customer_support"):
    result = decide(text, context, persona)
    print(f"{result.decision}: {result.reason}")
    if result.decision == APPROVE:
        mock_actions.run_for_persona(persona, text)
    else:
        print("[GATE] action not executed")
    return result


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit('usage: python3 wrapper.py <persona> "<text>" [context-json]')
    gate(sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}, sys.argv[1])
