import json
import mimetypes
import os
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import audit
import mock_actions
from wrapper import APPROVE, BLOCK, HOLD, decide

UI_DIR = Path(__file__).parent / "ui"
PERSONAS_DIR = Path(__file__).resolve().parent.parent / "personas"

PERSONAS = {"customer_support", "paralegal", "financial_analyst"}

# Reviewer choices on held items are logged next to the audit log. Logging only: a review never runs the action.
REVIEW_LOG = audit.LOG.parent / "review_log.jsonl"
_review_lock = threading.Lock()


def samples(persona):
    """Practice inputs (text and context only) so a UI can offer 'simulate from a test input'."""
    path = PERSONAS_DIR / persona / "practice_set.json"
    items = json.loads(path.read_text())["items"]
    return [{"id": i["id"], "text": i["text"], "context": i["context"]} for i in items]


def audit_tail(n=50):
    """Last n audit entries, parsed; unreadable lines are skipped so one bad line can't hide the trail."""
    if not audit.LOG.is_file():
        return []
    entries = []
    for line in audit.LOG.read_text().splitlines()[-n:]:
        try:
            entries.append(json.loads(line))
        except ValueError:
            pass
    return entries


def ui_file(path):
    """Static files from wrapper/ui/, so a team can use plain HTML, a built SPA, or anything a browser runs."""
    name = "persona.html" if path in ("/", "") else path.lstrip("/")
    target = (UI_DIR / name).resolve()
    if UI_DIR.resolve() not in target.parents or not target.is_file():
        return None
    return target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_json(self, code, body):
        raw = json.dumps(body, allow_nan=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        route, _, query = self.path.partition("?")
        if route == "/health":
            return self.send_json(200, {"status": "ok"})
        if route == "/api/samples":
            persona = dict(p.split("=", 1) for p in query.split("&") if "=" in p).get("persona")
            if persona not in PERSONAS:
                return self.send_json(400, {"error": "Unknown persona"})
            return self.send_json(200, {"samples": samples(persona)})
        if route == "/api/audit":
            return self.send_json(200, {"entries": audit_tail()})
        served = ui_file(route)
        if served:
            raw, content_type = served
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_json(404, {"error": "Unknown endpoint"})

    def read_payload(self):
        self.connection.settimeout(10)
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= 1_000_000:
            raise ValueError("Body must be 1 to 1000000 bytes")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("Body must be a JSON object")
        return payload

    def do_POST(self):
        if self.path == "/review":
            return self.review()
        if self.path != "/decide":
            return self.send_json(404, {"error": "Unknown endpoint"})
        try:
            payload = self.read_payload()
            text, persona, context = payload.get("text"), payload.get("persona"), payload.get("context", {})
            if not isinstance(text, str) or not text.strip() or len(text) > 20000:
                raise ValueError("text must be a non-empty string of at most 20000 characters")
            if not isinstance(persona, str) or persona not in PERSONAS:
                raise ValueError("Unknown persona")
            if not isinstance(context, dict):
                raise ValueError("context must be an object")
        except (ValueError, UnicodeDecodeError, OSError):
            return self.send_json(400, {"error": "Invalid request: supply text, persona, and an optional context object"})
        try:
            result = decide(text, context, persona)
            execute = result.decision == APPROVE
            if execute:
                mock_actions.run_for_persona(persona, text)
            self.send_json(200, {**asdict(result), "action_executed": execute})
        except Exception:
            self.send_json(500, {"error": "Wrapper failed; inspect the decision implementation"})

    def review(self):
        """Append a reviewer's choice to review_log.jsonl. It does NOT run the action or change the decision."""
        try:
            payload = self.read_payload()
            text, original = payload.get("input"), payload.get("original_decision")
            choice, reason = payload.get("reviewer_choice"), payload.get("reason")
            if not isinstance(text, str) or not text.strip() or len(text) > 20000:
                raise ValueError("input must be a non-empty string of at most 20000 characters")
            if original not in (APPROVE, HOLD, BLOCK):
                raise ValueError("original_decision must be APPROVE, HOLD_FOR_REVIEW, or BLOCK")
            if choice not in ("proceed", "reject"):
                raise ValueError("reviewer_choice must be proceed or reject")
            if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
                raise ValueError("reason must be a non-empty string of at most 2000 characters")
        except ValueError as e:
            return self.send_json(400, {"error": f"Invalid review: {e}"})
        except (UnicodeDecodeError, OSError):
            return self.send_json(400, {"error": "Invalid review: body must be a JSON object"})
        entry = {
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "input": text,
            "original_decision": original,
            "reviewer_choice": choice,
            "reason": reason.strip(),
        }
        with _review_lock, REVIEW_LOG.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        self.send_json(200, {"logged": True, "action_executed": False, **entry})


def main():
    host, port = os.getenv("HOST", "127.0.0.1"), int(os.getenv("PORT", "9000"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Approval Gate wrapper on http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
