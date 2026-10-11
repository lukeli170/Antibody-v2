"""Data models for Antibody v2 claim extraction and verification."""
from dataclasses import dataclass, field


@dataclass
class Claim:
    """A single legal claim extracted from an untrusted memo."""
    case_name: str | None          # Canonical or stated case name, or None if pure public-law
    citation: str | None           # Reporter citation (e.g. "384 U.S. 436") or None
    year: int | None               # Decision year (e.g. 1966) or None
    holding: str                   # The proposition asserted (e.g. holding or constitutional rule)
    quote: str                     # Exact verbatim substring from the memo
    start: int                     # Start offset in the memo (0-based)
    end: int                       # End offset in the memo (0-based)
    is_public_law: bool = False    # True if constitutional/public-law claim with no case citation

    def to_dict(self) -> dict:
        return {
            "case_name": self.case_name,
            "citation": self.citation,
            "year": self.year,
            "holding": self.holding,
            "quote": self.quote,
            "start": self.start,
            "end": self.end,
            "is_public_law": self.is_public_law,
        }


@dataclass
class SplitResult:
    """Result of splitting a memo into claims."""
    claims: list[Claim] = field(default_factory=list)
    raw_response: str | None = None
    source: str = "code"           # "model", "code", or "model+code_verified"
    flagged_injection: bool = False
    error: str | None = None

    @property
    def claim_count(self) -> int:
        return len(self.claims)

    def to_dict(self) -> dict:
        return {
            "claim_count": self.claim_count,
            "claims": [c.to_dict() for c in self.claims],
            "source": self.source,
            "flagged_injection": self.flagged_injection,
            "error": self.error,
        }

