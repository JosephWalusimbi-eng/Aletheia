#!/usr/bin/env python3
"""
server.py
=========
Aletheia - custom web front end.

Serves a single self-contained page and a small JSON API over Python's standard
library HTTP server. There is no web framework and no external asset: the page
carries its own CSS and JavaScript, so the interface loads instantly and works
with no internet connection.

Inference itself is unchanged. Every stage goes through the same
inference.aletheia.run_inference() used by the CLIs, so response times are
identical to running run.py directly. A lock serialises inference so two
requests never fight over the same CPU cores.
"""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inference.aletheia import build_prompt, parse_response, run_inference

UI_FILE = Path(__file__).resolve().parent / "ui" / "index.html"
HOST = "0.0.0.0"
PORT = 7860

VALID_STAGES = {
    "initial_with_followup",
    "test_recommendation",
    "advisory_conclusion",
}
STAGE_NEEDS_EXTRA = {
    "test_recommendation": "the follow-up answers",
    "advisory_conclusion": "the investigation results",
}

# llama.cpp already saturates every core, so running two inferences at once only
# makes both slower. Requests queue here instead.
_inference_lock = threading.Lock()


def run_stage(payload: dict) -> dict:
    stage = payload.get("stage", "initial_with_followup")
    if stage not in VALID_STAGES:
        raise ValueError(f"Unknown stage: {stage}")

    symptoms = [s.strip().lower() for s in payload.get("symptoms", "").split(",") if s.strip()]
    if not symptoms:
        raise ValueError("Enter at least one symptom.")

    extra = (payload.get("extra") or "").strip()
    if stage in STAGE_NEEDS_EXTRA and not extra:
        raise ValueError(f"This stage needs {STAGE_NEEDS_EXTRA[stage]}.")

    prompt = build_prompt(
        symptoms=symptoms,
        duration_days=int(payload.get("duration", 1)),
        age_group=payload.get("age", "adult"),
        sex=payload.get("sex", "unknown"),
        reasoning_type=stage,
        extra=extra,
    )

    with _inference_lock:
        raw, elapsed = run_inference(prompt, timeout=int(payload.get("timeout", 600)))

    return {"ok": True, "stage": stage, "elapsed": elapsed,
            "data": parse_response(raw), "raw": raw}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):        # keep the console clean
        pass

    def _send(self, code, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.html"):
            try:
                body = UI_FILE.read_bytes()
            except FileNotFoundError:
                self._send(500, b"UI file missing: " + str(UI_FILE).encode(), "text/plain")
                return
            self._send(200, body, "text/html; charset=utf-8")
        elif self.path == "/api/health":
            self._send(200, b'{"ok":true}', "application/json")
        else:
            self._send(404, b"Not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/stage":
            self._send(404, b"Not found", "text/plain")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._send(400, b'{"ok":false,"error":"Malformed request."}', "application/json")
            return

        try:
            result = run_stage(payload)
            code = 200
        except ValueError as exc:
            result, code = {"ok": False, "error": str(exc)}, 400
        except FileNotFoundError as exc:
            result, code = {"ok": False, "error": str(exc)}, 500
        except Exception as exc:
            result, code = {"ok": False, "error": f"Inference failed: {exc}"}, 500

        self._send(code, json.dumps(result).encode("utf-8"), "application/json")


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("\nAletheia is running.")
    print(f"Open http://localhost:{PORT} in your browser.")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
