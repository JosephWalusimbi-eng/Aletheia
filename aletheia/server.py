#!/usr/bin/env python3
"""
server.py
=========
Aletheia - custom web front end.

Serves a single self-contained page and a small JSON API over Python's standard
library HTTP server. There is no web framework and no external asset: the page
carries its own CSS and JavaScript, so the interface loads instantly and works
with no internet connection. Nothing here imports anything that is not in the
standard library, which is the point — a laptop that has finished installing
Aletheia never needs pip again.

Inference itself is unchanged. Every stage goes through the same
inference.aletheia code path used by the CLIs, so response times are identical
to running run.py directly. A lock serialises inference so two requests never
fight over the same CPU cores.

Three routes matter:

  GET  /api/status        what is actually loaded on this machine — model file,
                          size, threads — so the "runs offline on device" claim
                          is visible rather than asserted.
  POST /api/stage/stream  server-sent events: refused | token | result | error.
                          A stage takes 40-60 s; streaming means the reader sees
                          the answer being written instead of a still spinner.
  POST /api/stage         the original blocking JSON call, kept for scripts.
  POST /api/recall/*      lookup | save | delete against the saved-case store.
                          A stage the clinician has already seen and accepted
                          need not cost another 40-60 s of CPU to see again.
                          These routes report and record; they never decide.

Binding: 127.0.0.1 by default. This tool handles patient presentations, so it
is not exposed to the ward LAN unless someone deliberately sets ALETHEIA_HOST.
"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inference.aletheia import (
    build_prompt,
    parse_response,
    run_inference,
    runtime_info,
    stream_inference,
)
from inference.safety import HAZARD_CLASSES, HazardRefusal, screen
from inference import recall

UI_FILE = Path(__file__).resolve().parent / "ui" / "index.html"

# Loopback only. Set ALETHEIA_HOST=0.0.0.0 to reach the console from another
# machine on the same network, and understand that this puts patient
# presentations on that network before you do.
HOST = os.environ.get("ALETHEIA_HOST", "127.0.0.1")
PORT = int(os.environ.get("ALETHEIA_PORT", "7860"))

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


def case_inputs(payload: dict) -> dict:
    """Validate a request and return the inputs that define the situation.

    Shared by inference and by recall so the two can never disagree about what
    the clinician asked: a saved case is keyed on exactly the values that would
    have been sent to the model.

    Raises ValueError for bad input and HazardRefusal for a refused one. The
    screen runs here, which is what puts it ahead of recall as well as ahead of
    inference — a hazardous request is refused on a matched case exactly as it
    is on a cold run.
    """
    stage = payload.get("stage", "initial_with_followup")
    if stage not in VALID_STAGES:
        raise ValueError(f"Unknown stage: {stage}")

    raw_symptoms = payload.get("symptoms", "")
    symptoms = [s.strip().lower() for s in raw_symptoms.split(",") if s.strip()]
    if not symptoms:
        raise ValueError("Enter at least one symptom.")

    extra = (payload.get("extra") or "").strip()
    if stage in STAGE_NEEDS_EXTRA and not extra:
        raise ValueError(f"This stage needs {STAGE_NEEDS_EXTRA[stage]}.")

    # Screened on the text as typed, before the prompt exists and before the
    # case store is consulted.
    refusal = screen(raw_symptoms, extra)
    if refusal is not None:
        raise HazardRefusal(refusal)

    return {
        "stage": stage,
        "symptoms": symptoms,
        "duration_days": int(payload.get("duration", 1)),
        "age_group": payload.get("age", "adult"),
        "sex": payload.get("sex", "unknown"),
        "extra": extra,
        "raw_symptoms": raw_symptoms,
    }


def prepare(payload: dict) -> tuple[str, str, int]:
    """Validate a request and turn it into (stage, prompt, timeout)."""
    c = case_inputs(payload)
    prompt = build_prompt(
        symptoms=c["symptoms"],
        duration_days=c["duration_days"],
        age_group=c["age_group"],
        sex=c["sex"],
        reasoning_type=c["stage"],
        extra=c["extra"],
    )
    return c["stage"], prompt, int(payload.get("timeout", 600))


def run_stage(payload: dict) -> dict:
    """Blocking single-shot stage, kept for scripts and for /api/stage."""
    stage, prompt, timeout = prepare(payload)
    with _inference_lock:
        raw, elapsed = run_inference(prompt, timeout=timeout)
    return {"ok": True, "stage": stage, "elapsed": elapsed,
            "data": parse_response(raw, stage), "raw": raw}


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

    def _send_json(self, code, obj):
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json")

    # ---- server-sent events -------------------------------------------------
    # HTTP/1.1 needs a framing the client can follow when the body length is not
    # known up front, so the event stream is written as chunked transfer
    # encoding by hand. No framework, no dependency.

    def _open_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

    def _event(self, name: str, data: dict) -> bool:
        """Write one SSE event. Returns False once the browser has gone away."""
        frame = f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        body = frame.encode("utf-8")
        try:
            self.wfile.write(f"{len(body):X}\r\n".encode("ascii") + body + b"\r\n")
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return False

    def _close_stream(self):
        try:
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass

    # ---- routes -------------------------------------------------------------

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            try:
                body = UI_FILE.read_bytes()
            except FileNotFoundError:
                self._send(500, b"UI file missing: " + str(UI_FILE).encode(), "text/plain")
                return
            self._send(200, body, "text/html; charset=utf-8")
        elif path == "/api/health":
            self._send(200, b'{"ok":true}', "application/json")
        elif path == "/api/status":
            info = runtime_info()
            info.update({
                "ok": True,
                "ready": info["model_present"] and info["runner_present"],
                # Aletheia opens no outbound socket at any point. This is a
                # property of the code, not a probe result.
                "offline": True,
                "busy": _inference_lock.locked(),
                "hazard_classes": list(HAZARD_CLASSES),
            })
            try:
                info["recall"] = recall.stats()
            except Exception:
                info["recall"] = {"count": 0, "edited": 0, "stale": 0, "path": ""}
            self._send_json(200, info)
        else:
            self._send(404, b"Not found", "text/plain")

    def _read_payload(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/stage":
            self._post_stage()
        elif path == "/api/stage/stream":
            self._post_stage_stream()
        elif path == "/api/recall/lookup":
            self._post_recall_lookup()
        elif path == "/api/recall/save":
            self._post_recall_save()
        elif path == "/api/recall/delete":
            self._post_recall_delete()
        else:
            self._send(404, b"Not found", "text/plain")

    # ---- recall -------------------------------------------------------------
    # Three small routes, and none of them decides anything. Lookup reports
    # whether a record exists, save writes one the clinician asked to keep, and
    # delete removes one. What to do with a hit is the clinician's call, made in
    # the interface, every time.

    def _recall_guarded(self, handler):
        """Run a recall route with the same guards inference gets."""
        try:
            payload = self._read_payload()
        except Exception:
            self._send_json(400, {"ok": False, "error": "Malformed request."})
            return
        try:
            self._send_json(200, handler(payload))
        except HazardRefusal as exc:
            self._send_json(200, {"ok": False, "refused": exc.refusal.to_dict()})
        except ValueError as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            # A broken case store must never stop a clinician working: the
            # caller treats a failed lookup as a miss and runs the model.
            self._send_json(200, {"ok": False, "error": f"Case store unavailable: {exc}"})

    def _post_recall_lookup(self):
        def handler(payload):
            c = case_inputs(payload)          # screens before the store is read
            case = recall.lookup(
                c["symptoms"], c["duration_days"], c["age_group"],
                c["sex"], c["stage"], c["extra"],
            )
            if case is None:
                return {"ok": True, "hit": False}
            return {
                "ok": True,
                "hit": True,
                "case": case.to_dict(),
                "provenance": case.provenance(),
            }
        self._recall_guarded(handler)

    def _post_recall_save(self):
        def handler(payload):
            c = case_inputs(payload)
            data = payload.get("data")
            if not isinstance(data, dict) or not data:
                raise ValueError("Nothing to save.")

            # The schema collects no identity, so the free-text boxes are the
            # only way one could arrive. Warn once; the clinician decides.
            warning = recall.identifier_warning(c["raw_symptoms"], c["extra"])
            if warning and not payload.get("confirm"):
                return {"ok": False, "needs_confirmation": True, "warning": warning}

            case = recall.save(
                c["symptoms"], c["duration_days"], c["age_group"], c["sex"],
                c["stage"], data, c["extra"], edited=bool(payload.get("edited")),
            )
            return {"ok": True, "saved_on": case.saved_on,
                    "edited": case.edited, "key": case.key}
        self._recall_guarded(handler)

    def _post_recall_delete(self):
        def handler(payload):
            key = (payload.get("key") or "").strip()
            if not key:
                raise ValueError("No case key given.")
            return {"ok": True, "deleted": recall.delete(key)}
        self._recall_guarded(handler)

    def _post_stage(self):
        try:
            payload = self._read_payload()
        except Exception:
            self._send_json(400, {"ok": False, "error": "Malformed request."})
            return

        try:
            self._send_json(200, run_stage(payload))
        except HazardRefusal as exc:
            self._send_json(200, {"ok": False, "refused": exc.refusal.to_dict()})
        except ValueError as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
        except FileNotFoundError as exc:
            self._send_json(500, {"ok": False, "error": str(exc)})
        except Exception as exc:
            self._send_json(500, {"ok": False, "error": f"Inference failed: {exc}"})

    def _post_stage_stream(self):
        try:
            payload = self._read_payload()
        except Exception:
            self._send_json(400, {"ok": False, "error": "Malformed request."})
            return

        try:
            stage, prompt, timeout = prepare(payload)
        except HazardRefusal as exc:
            # A refusal is a normal, expected outcome, not an error: it opens
            # the stream and says so, so the console renders it the same way it
            # renders an answer.
            self._open_stream()
            self._event("refused", exc.refusal.to_dict())
            self._close_stream()
            return
        except ValueError as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
            return
        except FileNotFoundError as exc:
            self._send_json(500, {"ok": False, "error": str(exc)})
            return

        self._open_stream()

        # Someone else's stage may still be running. Say so rather than leaving
        # the reader looking at a stream that has gone quiet.
        if not _inference_lock.acquire(blocking=False):
            if not self._event("queued", {"message": "Another stage is running. Queued."}):
                return
            _inference_lock.acquire()

        try:
            stream = stream_inference(prompt, timeout=timeout)
            try:
                for kind, item in stream:
                    if kind == "token":
                        if not self._event("token", {"t": item}):
                            return        # browser closed; finally kills llama.cpp
                    else:
                        self._event("result", {
                            "stage": stage,
                            "elapsed": item["elapsed"],
                            "tokens": item["tokens"],
                            "tokens_per_second": item["tokens_per_second"],
                            "measured": item["measured"],
                            "data": parse_response(item["text"], stage),
                            "raw": item["text"],
                        })
            finally:
                stream.close()
        except TimeoutError as exc:
            self._event("error", {"message": str(exc)})
        except FileNotFoundError as exc:
            self._event("error", {"message": str(exc)})
        except Exception as exc:
            self._event("error", {"message": f"Inference failed: {exc}"})
        finally:
            _inference_lock.release()
            self._close_stream()


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    shown = "localhost" if HOST in ("127.0.0.1", "0.0.0.0") else HOST
    info = runtime_info()
    print("\nAletheia is running.")
    print(f"Open http://{shown}:{PORT} in your browser.")
    if not info["model_present"]:
        print("Warning: model file not found. Run: bash download_model.sh")
    if not info["runner_present"]:
        print("Warning: llama.cpp binary not found. Run: bash install.sh")
    if HOST == "0.0.0.0":
        print("Warning: bound to 0.0.0.0 — reachable from the whole network.")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
