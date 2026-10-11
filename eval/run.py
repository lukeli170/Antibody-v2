#!/usr/bin/env python3
"""Execute test memos against the Approval Gate wrapper POST /decide.

Sends memos to the wrapper, supports --runs N repetitions for stability measurement,
and saves detailed timing, decisions, and reasons to eval/results.json.
"""
import argparse
import http.client
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SUITE_PATH = REPO / "eval" / "suite.json"
RESULTS_PATH = REPO / "eval" / "results.json"


def find_active_wrapper_url() -> str | None:
    """Find a running wrapper serving GET /health on localhost."""
    # Check default port 9000 first
    candidates = [9000]

    # Search for other listening Python processes on macOS/Linux
    try:
        import subprocess
        output = subprocess.check_output(
            ["lsof", "-iTCP", "-sTCP:LISTEN", "-n", "-P"],
            text=True, stderr=subprocess.DEVNULL
        )
        for line in output.splitlines():
            if "Python" in line or "python" in line:
                m = re.search(r":(\d+)\s+\(LISTEN\)", line)
                if m:
                    port = int(m.group(1))
                    if port not in candidates and port != 11434:  # ignore ollama
                        candidates.append(port)
    except Exception:
        pass

    for port in candidates:
        url = f"http://127.0.0.1:{port}"
        try:
            req = urllib.request.Request(f"{url}/health")
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                data = json.loads(resp.read().decode())
                if data.get("status") == "ok":
                    return url
        except Exception:
            continue
    return None


def call_decide(base_url: str, text: str, context: dict, persona: str, timeout: float) -> dict:
    """POST /decide and record response, timing, and errors."""
    url = f"{base_url.rstrip('/')}/decide"
    payload = json.dumps({"text": text, "context": context or {}, "persona": persona}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = time.monotonic() - start
            body = json.loads(resp.read().decode("utf-8"))
            return {
                "ok": True,
                "decision": body.get("decision", "ERROR"),
                "reason": body.get("reason", ""),
                "seconds": round(elapsed, 4),
                "action_executed": body.get("action_executed"),
                "evidence": body.get("evidence", []),
            }
    except Exception as e:
        elapsed = time.monotonic() - start
        return {
            "ok": False,
            "decision": "ERROR",
            "reason": f"Request failed: {type(e).__name__}: {e}",
            "seconds": round(elapsed, 4),
            "action_executed": False,
            "evidence": [],
        }


def run_item_runs(item: dict, base_url: str, num_runs: int, persona: str, timeout: float) -> dict:
    """Run a single test memo num_runs times and aggregate results."""
    run_records = []
    for r_idx in range(num_runs):
        res = call_decide(base_url, item["text"], item.get("context", {}), persona, timeout)
        res["run_index"] = r_idx
        run_records.append(res)

    decisions = [r["decision"] for r in run_records]
    # Majority decision
    counts = {}
    for d in decisions:
        counts[d] = counts.get(d, 0) + 1
    majority_decision = max(counts, key=counts.get)
    majority_reason = next(r["reason"] for r in run_records if r["decision"] == majority_decision)

    avg_seconds = round(sum(r["seconds"] for r in run_records) / len(run_records), 4)
    stable = len(set(decisions)) == 1

    return {
        **item,
        "runs": run_records,
        "decision": majority_decision,
        "reason": majority_reason,
        "seconds": avg_seconds,
        "decisions": decisions,
        "stable": stable,
        "changed": not stable,
    }


def execute_suite(
    suite_items: list,
    base_url: str,
    num_runs: int = 1,
    persona: str = "paralegal",
    workers: int = 4,
    timeout: float = 30.0,
) -> list:
    """Execute evaluation items across multiple workers."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(
            pool.map(
                lambda item: run_item_runs(item, base_url, num_runs, persona, timeout),
                suite_items,
            )
        )
    return results


def main():
    parser = argparse.ArgumentParser(description="Run Antibody v2 evaluation against wrapper")
    parser.add_argument("--suite", default=str(SUITE_PATH), help="Path to suite JSON")
    parser.add_argument("--split", choices=["tune", "heldout", "all"], default="all", help="Split to run")
    parser.add_argument("--runs", type=int, default=1, help="Repetitions per memo for stability checking")
    parser.add_argument("--url", default=None, help="Wrapper URL (auto-detected if omitted)")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent workers")
    parser.add_argument("--timeout", type=float, default=30.0, help="Timeout per request in seconds")
    parser.add_argument("--output", default=str(RESULTS_PATH), help="Path to save results JSON")
    parser.add_argument("--spawn", action="store_true", help="Spawn runner.Stack instead of connecting to running wrapper")
    args = parser.parse_args()

    suite_file = Path(args.suite)
    if not suite_file.exists():
        sys.exit(f"Suite file not found at {suite_file}. Run eval/mutate.py first.")

    suite = json.loads(suite_file.read_text(encoding="utf-8"))
    if args.split != "all":
        suite = [item for item in suite if item["split"] == args.split]

    print(f"Loaded {len(suite)} items for split: {args.split}")

    wrapper_url = args.url
    stack_ctx = None

    if args.spawn or not wrapper_url:
        discovered = None if args.spawn else find_active_wrapper_url()
        if discovered:
            wrapper_url = discovered
            print(f"Connected to existing running wrapper at {wrapper_url}")
        else:
            print("No running wrapper found. Spawning private test stack (runner.Stack)...")
            sys.path.insert(0, str(REPO))
            from harness import runner
            stack_ctx = runner.Stack(latency="0")
            stack = stack_ctx.__enter__()
            wrapper_url = stack.wrapper_url
            print(f"Spawned wrapper stack at {wrapper_url}")

    try:
        t0 = time.monotonic()
        results = execute_suite(
            suite,
            base_url=wrapper_url,
            num_runs=args.runs,
            persona="paralegal",
            workers=args.workers,
            timeout=args.timeout,
        )
        total_time = round(time.monotonic() - t0, 2)
        print(f"Executed {len(results)} items in {total_time}s across {args.workers} workers.")

        output_data = {
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "url": wrapper_url,
                "split": args.split,
                "runs": args.runs,
                "workers": args.workers,
                "total_items": len(results),
                "total_time_seconds": total_time,
            },
            "items": results,
        }

        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(output_data, indent=2), encoding="utf-8")
        print(f"Saved results to {out_path}")

    finally:
        if stack_ctx:
            stack_ctx.__exit__(None, None, None)


if __name__ == "__main__":
    main()

