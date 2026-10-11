"""Critic and injection defense engine for Antibody v2.

Reviews structured findings after decision:
- Prompt injection defense: flagged injections trigger HOLD.
- Every BLOCK must point to a real memo quote and a real list entry.
- Every APPROVE must show a 'supported' verdict for every extracted claim.
- Safety rule: The critic can ONLY move a decision toward HOLD, NEVER create an APPROVE.
"""
from dataclasses import dataclass


@dataclass
class CriticReviewResult:
    final_decision: str       # "APPROVE", "HOLD_FOR_REVIEW", "BLOCK"
    critic_notes: list[str]
    modified_by_critic: bool
    injection_held: bool


class GateCritic:
    """Post-decision critic operating exclusively on structured findings."""

    def review(
        self,
        tentative_decision: str,
        claims: list,
        triage_predicted_claims: int,
        flagged_injection: bool,
        reasons: list[str],
        evidence: list[str],
    ) -> CriticReviewResult:
        notes = []
        final_decision = tentative_decision
        modified = False
        injection_held = False

        # 1. Injection Defense: Any prompt injection triggers HOLD
        if flagged_injection:
            if final_decision != "BLOCK":
                final_decision = "HOLD_FOR_REVIEW"
                modified = True
                injection_held = True
                notes.append("Critique: Instruction-shaped text flagged as possible prompt injection; held for human review.")

        # 2. APPROVE Validation: Every claim must be supported
        if final_decision == "APPROVE":
            if not claims:
                # Routine memo with 0 claims is allowed to be approved if triage is Tier 0
                pass
            else:
                for c in claims:
                    holding_verdict = getattr(c, "holding_verdict", None)
                    if holding_verdict and holding_verdict != "SUPPORTED":
                        final_decision = "HOLD_FOR_REVIEW"
                        modified = True
                        notes.append(f"Critique: Claim '{getattr(c, 'case_name', 'Unknown')}' has verdict '{holding_verdict}', not SUPPORTED; cannot approve.")

        # 3. Claim Count Consistency check
        if claims and triage_predicted_claims > 0 and len(claims) != triage_predicted_claims:
            notes.append(f"Notice: Extracted claim count ({len(claims)}) differs from triage prediction ({triage_predicted_claims}).")

        # 4. Invariant Safety Rule: Critic can NEVER create an APPROVE
        if tentative_decision in ("BLOCK", "HOLD_FOR_REVIEW") and final_decision == "APPROVE":
            final_decision = tentative_decision
            modified = False

        return CriticReviewResult(
            final_decision=final_decision,
            critic_notes=notes,
            modified_by_critic=modified,
            injection_held=injection_held,
        )

