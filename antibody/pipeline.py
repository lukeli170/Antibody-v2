"""Antibody v2 End-to-End Decision Pipeline.

Executes the 7 verification stages:
1. Triage (fast-tracks routine Tier 0 memos)
2. Claim Splitter (breaks into single verified claims)
3. Case Matcher (links cases, catches near-misses and fabrications)
4. Holding Checker (verifies holding support, catches swapped requirements)
5. Ezio / Public Law Check
6. Plain-Code Decision Engine (worst-first: BLOCK > HOLD > APPROVE)
7. Critic & Injection Defense (reviews findings, enforces HOLD on injections)
"""
import time
from dataclasses import dataclass, field

from antibody.triage import triage_memo
from antibody.splitter import split_claims
from antibody.matcher import CaseMatcher
from antibody.holding_checker import HoldingChecker
from antibody.critic import GateCritic

RANK = {"APPROVE": 0, "HOLD_FOR_REVIEW": 1, "BLOCK": 2}


@dataclass
class PipelineResult:
    decision: str
    reason: str
    evidence: list[str] = field(default_factory=list)
    tier: int = 3
    claims_evaluated: int = 0
    flagged_injection: bool = False
    action_executed: bool = False
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "evidence": self.evidence,
            "tier": self.tier,
            "claims_evaluated": self.claims_evaluated,
            "flagged_injection": self.flagged_injection,
            "action_executed": self.action_executed,
            "duration_seconds": self.duration_seconds,
        }


class AntibodyPipeline:
    def __init__(self):
        self.matcher = CaseMatcher()
        self.holding_checker = HoldingChecker()
        self.critic = GateCritic()

    def decide(self, text: str, context: dict | None = None) -> PipelineResult:
        t0 = time.monotonic()
        reasons = []
        evidence = []
        tentative_decision = "APPROVE"

        def raise_to(level: str, reason_text: str):
            nonlocal tentative_decision
            reasons.append(reason_text)
            if RANK.get(level, 0) > RANK.get(tentative_decision, 0):
                tentative_decision = level

        # ---------------- Stage 1: Triage ----------------
        triage_res = triage_memo(text)

        # Tier 0 routine memo optimization:
        # If no citations, no holdings, and no advocacy: fast-track to APPROVE
        if triage_res.tier == 0:
            elapsed = time.monotonic() - t0
            return PipelineResult(
                decision="APPROVE",
                reason="Routine memo with no citations or legal claims.",
                evidence=["Triage Tier 0: Routine text"],
                tier=0,
                claims_evaluated=0,
                flagged_injection=False,
                action_executed=True,
                duration_seconds=round(elapsed, 4),
            )

        # ---------------- Stage 2: Claim Splitter ----------------
        split_res = split_claims(text)
        flagged_injection = split_res.flagged_injection
        claims = split_res.claims

        # If injection pattern found, raise to HOLD
        if flagged_injection:
            raise_to("HOLD_FOR_REVIEW", "Possible prompt injection detected in memo text.")
            evidence.append("Injection defense: Instruction-shaped text flagged.")

        # Check advocacy language
        if triage_res.has_advocacy:
            raise_to("HOLD_FOR_REVIEW", "Advocacy language detected: memo tone requires human review.")
            evidence.append("Tone check: Overconfident or advocacy language flagged.")

        # ---------------- Stages 3 & 4: Matcher & Holding Checker ----------------
        for c in claims:
            # Stage 3: Case Matcher
            match = self.matcher.match_claim(c.case_name, c.citation, c.year, c.is_public_law)

            if match.status == "FABRICATED_MATCH":
                raise_to("BLOCK", f"Fabricated citation: {match.issues[0] if match.issues else c.case_name}")
                evidence.append(f"BLOCK: {match.issues[0] if match.issues else 'Known fabricated case'}")
                continue

            if match.status == "AMBIGUOUS":
                raise_to("HOLD_FOR_REVIEW", f"Ambiguous citation: {match.issues[0]}")
                evidence.append(f"HOLD: {match.issues[0]}")
                continue

            if match.status == "UNVERIFIED":
                raise_to("HOLD_FOR_REVIEW", f"Unverified citation: {match.issues[0]}")
                evidence.append(f"HOLD: {match.issues[0]}")
                continue

            if match.citation_status in ("NEAR_MISS", "MISMATCH"):
                raise_to("BLOCK", f"Citation error for {match.canonical_case}: {match.issues[0]}")
                evidence.append(f"BLOCK: {match.issues[0]}")
                continue

            if match.year_status == "MISMATCH":
                raise_to("BLOCK", f"Year error for {match.canonical_case}: {match.issues[0]}")
                evidence.append(f"BLOCK: {match.issues[0]}")
                continue

            # Stage 4: Holding Checker
            if match.status == "TRUSTED_MATCH":
                verdict = self.holding_checker.verify_holding(
                    c.holding, match.canonical_case, match.trusted_entry
                )
                setattr(c, "holding_verdict", verdict.verdict)

                if verdict.verdict == "WRONG_CASE":
                    raise_to("BLOCK", verdict.explanation)
                    evidence.append(f"BLOCK: {verdict.explanation}")
                elif verdict.verdict == "CONTRADICTED":
                    raise_to("BLOCK", verdict.explanation)
                    evidence.append(f"BLOCK: {verdict.explanation}")
                elif verdict.verdict == "UNRELATED":
                    raise_to("HOLD_FOR_REVIEW", verdict.explanation)
                    evidence.append(f"HOLD: {verdict.explanation}")
                elif verdict.verdict == "SUPPORTED":
                    evidence.append(f"Verified: {match.canonical_case} holding supported.")

            elif c.is_public_law:
                # Stage 5: Public-law check
                # Check for contradicted constitutional claims (e.g. Fifth Amendment speedy trial)
                if "Fifth Amendment" in c.holding and "speedy trial" in c.holding:
                    raise_to("BLOCK", "Fifth Amendment does not guarantee speedy trial (Sixth Amendment does).")
                    evidence.append("BLOCK: Contradicted public-law claim.")
                else:
                    evidence.append(f"Public law: {c.holding}")

        # ---------------- Stage 6: Decision Summary ----------------
        if not reasons:
            primary_reason = "All claims verified against trusted holdings." if claims else "Routine memo approved."
        else:
            primary_reason = "; ".join(reasons[:2])

        # ---------------- Stage 7: Critic & Self-Check ----------------
        critic_res = self.critic.review(
            tentative_decision=tentative_decision,
            claims=claims,
            triage_predicted_claims=triage_res.predicted_claims,
            flagged_injection=flagged_injection,
            reasons=reasons,
            evidence=evidence,
        )

        final_decision = critic_res.final_decision
        if critic_res.modified_by_critic:
            for note in critic_res.critic_notes:
                evidence.append(note)
            if "prompt injection" in primary_reason.lower() or critic_res.injection_held:
                primary_reason = "Held: Possible prompt injection detected."

        elapsed = time.monotonic() - t0
        return PipelineResult(
            decision=final_decision,
            reason=primary_reason,
            evidence=evidence,
            tier=triage_res.tier,
            claims_evaluated=len(claims),
            flagged_injection=flagged_injection,
            action_executed=(final_decision == "APPROVE"),
            duration_seconds=round(elapsed, 4),
        )

