#!/usr/bin/env python3
"""Run fresh paralegal probes sequentially; all generated files stay in redteam/."""
import hashlib
import json
import os
import re
import shlex
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DECISIONS = {"APPROVE", "HOLD_FOR_REVIEW", "BLOCK"}


def parse_result(output):
    decision = re.search(r"^decision:\s+(APPROVE|HOLD_FOR_REVIEW|BLOCK)(?:\s|$)", output, re.M)
    reason = re.search(r"^reason:[ \t]*(.*?)(?=^action:|\Z)", output, re.M | re.S)
    if not decision or not reason or not reason.group(1).strip():
        raise ValueError("gate.py returned no valid decision and non-empty reason")
    return decision.group(1), reason.group(1).strip()


def classify(expected, got):
    if expected == got:
        return "PASS"
    if expected in {"BLOCK", "HOLD_FOR_REVIEW"} and got in {"BLOCK", "HOLD_FOR_REVIEW"}:
        return "caught, wrong label"
    return "FAIL"


def cell(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def fingerprint():
    digest = hashlib.sha256()
    for name in ("wrapper.py", "policy.json", "serve.py", "ezio_client.py", "audit.py", "mock_actions.py"):
        digest.update(name.encode() + b"\0" + (REPO / "wrapper" / name).read_bytes())
    return digest.hexdigest()


def self_check():
    assert parse_result("decision: BLOCK  (0.1s)\nreason:   Bad citation.\naction:   not executed\n") == ("BLOCK", "Bad citation.")
    for expected in DECISIONS:
        for got in DECISIONS | {"ERROR"}:
            status = classify(expected, got)
            assert (status == "PASS") == (expected == got)
            assert (status == "caught, wrong label") == (expected != got and expected != "APPROVE" and got in {"BLOCK", "HOLD_FOR_REVIEW"})
    for malformed in ("", "decision: MAYBE\nreason: unsure\n", "decision: APPROVE\nreason:  \naction: EXECUTED\n"):
        try:
            parse_result(malformed)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid CLI output was accepted")
    assert cell("a|b\nc") == "a\\|b<br>c"


def main():
    self_check()
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases.json must contain a non-empty list")
    ids = set()
    for case in cases:
        for key in ("id", "memo", "expected_decision", "why", "rule"):
            if not isinstance(case.get(key), str) or not case[key].strip():
                raise ValueError("each case needs non-empty id, memo, expected_decision, why, and rule")
        if case["expected_decision"] not in DECISIONS or case["id"] in ids:
            raise ValueError("case decisions must be valid and ids unique")
        ids.add(case["id"])

    logs = HERE / "logs"
    logs.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(logs))
    # gate.py try clears inherited GATE_LOG_DIR; its startup override restores it.
    env["GATE_WRAPPER_CMD"] = shlex.join(["env", "GATE_LOG_DIR=" + str(logs), "python3", "wrapper/serve.py"])
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    before = fingerprint()
    lines = ["| Case id | Expected | Got | PASS/FAIL | Reason |", "|---|---|---|---|---|"]
    for line in lines:
        print(line, flush=True)
    counts = Counter()
    failures = defaultdict(list)
    with (logs / "gate-output.log").open("w", encoding="utf-8") as transcript:
        for case in cases:
            command = ["python3", "gate.py", "try", "--persona", "paralegal", case["memo"]]
            try:
                result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
                transcript.write("\n=== " + case["id"] + " ===\n" + result.stdout + result.stderr)
                transcript.flush()
                if result.returncode:
                    got, reason = "ERROR", "CLI exit {}: {}".format(result.returncode, (result.stdout + result.stderr).strip())
                else:
                    got, reason = parse_result(result.stdout)
            except (OSError, ValueError) as error:
                got, reason = "ERROR", str(error)
                transcript.write("\n=== " + case["id"] + " ERROR ===\n" + reason + "\n")
                transcript.flush()
            status = classify(case["expected_decision"], got)
            counts[status] += 1
            if status == "FAIL":
                failures["Execution or response errors" if got == "ERROR" else case["rule"]].append(case["id"])
            row = "| " + " | ".join(cell(value) for value in (case["id"], case["expected_decision"], got, status, reason)) + " |"
            lines.append(row)
            print(row, flush=True)

    summary = "{} cases: {} PASS, {} caught, wrong label, {} FAIL.".format(len(cases), counts["PASS"], counts["caught, wrong label"], counts["FAIL"])
    lines.extend(["", summary, "", "FAILs by general rule:"])
    lines.extend("- {}: {}".format(rule, ", ".join(ids)) for rule, ids in sorted(failures.items()))
    if not failures:
        lines.append("- None.")
    after = fingerprint()
    lines.extend(["", "Started (UTC): " + started, "Wrapper decision-path SHA-256 before: " + before, "Wrapper decision-path SHA-256 after: " + after])
    if before != after:
        lines.append("Wrapper files changed during the run; rows may reflect different revisions.")
    lines.extend(["", "Ran python3 gate.py try --persona paralegal <memo> sequentially, using the supported wrapper startup override only to keep logs inside redteam/.", "No wrapper fixes, practice/final evaluation, UI checks, or failure-mode drills were performed."])
    (HERE / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines[len(cases) + 2:]), flush=True)
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
