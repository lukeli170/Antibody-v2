# Antibody v2

**A Neuro-Symbolic, Claim-Level Verification Gate for Legal AI Systems**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.md)
[![Tests: 45 passed](https://img.shields.io/badge/tests-45%20passed-brightgreen.svg)]()
[![Unsafe Approvals: 0.0%](https://img.shields.io/badge/unsafe%20approvals-0.0%25-brightgreen.svg)]()

Antibody was originally created as a hackathon project—where our prototype achieved a perfect 50/50 score on benchmark practice case tests—and was subsequently re-architected into a full claim-level verification gate. It acts as an autonomous safety firewall between generative AI models and mission-critical legal workflows, enforcing deterministic verification before any memorandum or court filing can be executed or submitted.

---

## The Problem: Why Generative AI Fails in Law

Large language models deployed in paralegal and legal drafting workflows introduce critical failure modes that whole-document heuristics and simple confidence scores cannot reliably detect:

1. **Hallucinated Precedents & Near-Miss Citations:** Models invent non-existent case reporters or misattribute real case names to subtly incorrect volumes, reporters, or decision years (e.g., claiming *Miranda v. Arizona* was decided in 1968 rather than 1966).
2. **Holding Inversions & Scope Creep:** Models frequently drop negative particles or swap doctrinal standards—asserting, for example, that *"Miranda requires a warrant"* or that evidence obtained via unlawful search *"may be admitted in state courts"*.
3. **Prompt Injection & Adversarial Bypass:** Memos containing user-submitted or adversarial instructions can hijack the model's output to emit fake approvals or suppress validation warnings.

---

## Core Philosophy: Neuro-Symbolic Decision Making

> **"AI extracts and compares; plain code decides."**

Antibody rejects the approach of trusting an LLM or black-box score to make binding go/no-go decisions. Instead, Antibody uses language models and fuzzy extractors strictly as **untrusted feature extractors**. Final policy evaluations are governed by **deterministic, audited code invariants**:

* **One-Way Ratchet:** Any signal of uncertainty, contradiction, or data degradation routes strictly toward `HOLD_FOR_REVIEW` or `BLOCK`, never toward `APPROVE`.
* **Zero Unsafe Approvals Priority:** Catching invalid or inverted law is treated as an absolute priority over automated throughput.
* **Deterministic Audit Trail:** Every decision emits a structured JSON record with precise timestamps, verbatim citation spans, matched case records, and mathematical similarity scores.

```
Incoming Legal Memo
       │
       ▼
┌────────────────────────────────────────────────────────┐
│  Tier 0-3 Adaptive Triage Engine                       │
│  - Routine memos: sub-millisecond fast path            │
│  - Memos with citations: routed to deep verification   │
└──────────────────────┬─────────────────────────────────┘
                       │
       ▼               ▼                ▼
┌─────────────┐ ┌──────────────┐ ┌──────────────────────┐
│ Claim       │ │ Fuzzy Case   │ │ Holding Verification │
│ Splitter    │ │ Matcher      │ │ & Inversion Checker  │
│ (Regex &    │ │ (RapidFuzz & │ │ (Semantic support,   │
│ Abbr-Safe)  │ │ Token Dist)  │ │  negation detection) │
└──────┬──────┘ └──────┬───────┘ └──────────┬───────────┘
       │               │                    │
       └───────────────┼────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────┐
│  Adversarial Critic & Injection Defense                │
│  - Detects prompt injection & instruction overrides    │
│  - One-way demotion: can only HOLD, never APPROVE      │
└──────────────────────┬─────────────────────────────────┘
                       │
                       ▼
         Deterministic Decision Policy
    [ APPROVE  │  HOLD_FOR_REVIEW  │  BLOCK ]
```

---

## System Architecture

### 1. Atomic Claim Splitter (`antibody/splitter.py`)
Standard sentence tokenizers fail on legal citations due to abbreviations like `v.`, `U.S.`, `F.3d`, `Co.`, and `No.`. The claim splitter combines abbreviation-aware boundary detection with legal citation regexes to isolate every case citation and its asserted holding into independent verification pairs.

### 2. Fuzzy Case & Citation Matcher (`antibody/matcher.py`)
Matches cited precedents against a trusted corpus of legal authorities:
* Computes normalized Levenshtein ratios and token-sort similarity.
* Catches near-miss citations (e.g., `384 U.S. 438` instead of `384 U.S. 436`).
* Detects decision year mismatches and fabricated case names.

### 3. Holding Verification Engine (`antibody/holding_checker.py`)
Determines whether the memorandum accurately states the proposition of law:
* **Affirmative Support:** Verifies substantive token overlap and semantic agreement against the authoritative holding.
* **Negation & Inversion Detection:** Flags flipped requirements, dropped negative particles, and contrast clauses (`rather than`, `instead of`).
* **Scope Expansions:** Flags attempts to broaden narrow procedural holdings into general common-law doctrines.

### 4. Adversarial Critic & Injection Defense (`antibody/critic.py`)
Inspects incoming drafts for jailbreaks, prompt injections, and system prompt leakage attempts. The critic enforces a one-way safety barrier: it can downgrade a candidate approval to `HOLD_FOR_REVIEW`, but can never elevate a held or blocked decision to approval.

### 5. Four-Tier Adaptive Triage Engine (`antibody/triage.py`)
Balances latency with exhaustive safety:
* **Tier 0 (< 1 ms):** Fast-tracks routine procedural memos without legal citations.
* **Tier 1 (Fast Path):** Exact matches against pre-indexed authoritative holdings.
* **Tier 2 (Deep Verification):** Full fuzzy extraction and semantic holding verification.
* **Tier 3 (High Risk / Novel):** Adversarial inspection and fail-safe routing to human review.

---

## Benchmark & Evaluation Results

Tested against a 108-item mutated legal memorandum benchmark (`eval/suite.json`) consisting of 55 tuning cases and 53 held-out test cases with subtle citation errors, inverted holdings, and prompt injections:

| Metric | Target | Antibody v2 Result |
| :--- | :---: | :---: |
| **Unsafe Approvals** (Bad memos approved) | **0.0%** | **0.0%** (0 / 83) |
| **Good Memos Stopped** (Valid memos blocked) | **< 5.0%** | **0.0%** (0 / 25) |
| **Automation Rate** | **> 70.0%** | **81.5%** |
| **Stability Flips** (5 consecutive runs) | **0** | **0 / 53 (100% stable)** |
| **Practice Set Accuracy** | **16 / 16** | **16 / 16 exact** |
| **Resilience & Failure Drills** | **15.0 / 15** | **15.0 / 15** |
| **Weighted Error Cost** | **0** | **0** (down from 160 in baseline) |

*Failure drills test graceful degradation under 6 operational failure modes: network down, rate-limited, 503 server error, malformed payloads, unavailable upstream signals, and slow latency.*

---

## Getting Started

### Prerequisites
* Python 3.9+
* Recommended: Virtual environment (`.venv`)

### Installation

```bash
git clone https://github.com/lukeli170/Antibody-v2.git
cd Antibody-v2

# Install dependencies (Rapidfuzz for high-speed Levenshtein matching)
pip install rapidfuzz pytest
```

### Running the Live Gate & UI

Launch the verification gate and interactive dashboard with a single command:

```bash
# Using the installed terminal runner
antibody

# Or via Python directly
python3 gate.py serve --persona paralegal
```

Open your browser to:
* **Interactive Studio & Audit Inspector:** `http://127.0.0.1:<PORT>/antibody.html`
* **Paralegal Workflow UI:** `http://127.0.0.1:<PORT>/persona.html`

---

## CLI Reference

The repo includes a unified `antibody` CLI wrapper:

```bash
# Test an individual legal memorandum
antibody try "Under Miranda v. Arizona, 384 U.S. 436 (1966), custodial statements require warnings."

# Run 16-item practice suite & 6 failure drills
antibody practice

# Run the 108-item verification benchmark suite
antibody eval

# Run all unit and contract tests (45 tests)
antibody test

# Open local visual test results viewer
antibody results
```

---

## Repository Structure

```
Approval-Gate/
├── antibody/                  # Core Antibody v2 Engine
│   ├── splitter.py            # Abbreviation-safe claim & citation splitter
│   ├── matcher.py             # RapidFuzz case & citation matcher
│   ├── holding_checker.py     # Semantic holding & inversion checker
│   ├── triage.py              # 4-tier adaptive latency triage
│   ├── critic.py              # Prompt injection defense & one-way demotion
│   └── models.py              # Dataclasses & type definitions
├── wrapper/                   # Gateway HTTP server & UI
│   ├── wrapper.py             # Decision pipeline integration
│   ├── serve.py               # HTTP server exposing POST /decide
│   └── ui/                    # Front-end interfaces
│       ├── antibody.html      # Real-time claim inspector & test studio
│       └── persona.html       # Paralegal drafting simulator
├── eval/                      # Evaluation & Benchmarking Harness
│   ├── mutate.py              # Systematic adversarial mutation generator
│   ├── run.py                 # Multi-run evaluation executor
│   ├── suite.json             # 108-item benchmark dataset
│   └── report_v2.md           # Benchmark evaluation results
├── tests/                     # Test Suite (pytest)
│   ├── test_splitter.py       # Claim extraction tests
│   ├── test_matcher.py        # Case matching & near-miss tests
│   └── test_holding_checker.py# Holding inversion & negation tests
├── bin/antibody               # Native terminal executable
└── gate.py                    # Gateway orchestrator & drill runner
```

---

## License

This project is licensed under the [MIT License](LICENSE.md).
