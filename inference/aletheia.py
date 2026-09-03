"""
aletheia.py
===========
Core inference wrapper for Aletheia Diagnostic AI.
Three-stage clinical pipeline:
  Stage 1 (initial_with_followup)  — tentative differential + follow-up questions to ask the clinician
  Stage 2 (test_recommendation)    — priority investigations after follow-up answers (headline output)
  Stage 3 (advisory_conclusion)    — management advisory after test results (doctor decides)
"""

import codecs
import subprocess
import json
import os
import re
import threading
import time
from collections.abc import Iterator
from pathlib import Path

try:  # imported as a package (server, run.py, cli.py)
    from inference.safety import HazardRefusal, screen
except ImportError:  # this file executed directly
    from safety import HazardRefusal, screen

CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {
        "llama_cli": str(Path.home() / "llama.cpp/build/bin/llama-cli"),
        "model_path": str(Path(__file__).parent.parent / "model/aletheia_q4km.gguf"),
        "context_size": 1024,
        "threads": os.cpu_count() or 4,
        "max_tokens": 512,
        "temperature": 0.1,
    }


CONFIG = load_config()

SYSTEM_PROMPT = (
    "You are Aletheia, an offline-first clinical decision support AI "
    "designed for district hospitals and health centres in sub-Saharan Africa. "
    "You support — not replace — the treating clinician. "
    "Always respond in structured JSON format."
)


def build_prompt(
    symptoms: list[str],
    duration_days: int,
    age_group: str = "adult",
    sex: str = "unknown",
    reasoning_type: str = "initial_with_followup",
    extra: str = "",
) -> str:
    """
    Build a structured clinical prompt for one of three pipeline stages.

    reasoning_type:
        'initial_with_followup'  — Stage 1: tentative differential + follow-up questions (no tests yet)
        'test_recommendation'    — Stage 2: priority tests as primary output (extra = follow-up answers)
        'advisory_conclusion'    — Stage 3: management advisory, doctor decides (extra = investigation results)
    """
    base_input = {
        "symptoms": symptoms,
        "duration_days": duration_days,
        "patient_age_group": age_group,
        "sex": sex,
    }

    if reasoning_type == "initial_with_followup":
        instruction = (
            "Analyze this patient presentation. "
            "List the most likely differential diagnoses with probability estimates and severity. "
            "Then identify 3 to 5 targeted follow-up questions the clinician must answer to narrow the differential. "
            "Do NOT recommend diagnostic tests yet — tests come after the follow-up answers are collected. "
            "Output JSON with these exact keys: "
            "tentative_differentials (list of objects with keys condition, probability 0.0-1.0, "
            "severity one of Critical|High|Moderate|Low), "
            "follow_up_questions (list of strings), "
            "red_flags (list of strings — signs requiring immediate escalation), "
            "clinical_rationale (string)."
        )
        input_block = json.dumps(base_input)

    elif reasoning_type == "test_recommendation":
        instruction = (
            "Based on the patient presentation and the clinician's follow-up answers, "
            "recommend the priority diagnostic investigations the clinician must perform next. "
            "The recommended_tests list is your PRIMARY output — it must come first in your JSON and be specific. "
            "Include the working differential as supporting context only to explain why these tests are chosen. "
            "Do NOT state a confirmed diagnosis — the tests have not been done yet. "
            "Output JSON with these exact keys: "
            "recommended_tests (list of strings in priority order — this is the main output), "
            "working_differential (list of objects with keys condition, probability 0.0-1.0 — context only), "
            "rationale_for_tests (string explaining how the tests address the differential)."
        )
        input_block = json.dumps({**base_input, "follow_up_answers": extra})

    elif reasoning_type == "advisory_conclusion":
        instruction = (
            "Given the investigation results, provide clinical decision support to help the treating clinician "
            "decide on management. "
            "Your output is ADVISORY — the treating clinician makes every final management decision. "
            "Do not issue a treatment order. Present options and reasoning for the clinician to evaluate. "
            "Output JSON with these exact keys: "
            "likely_diagnosis (string), "
            "diagnostic_confidence (string: High|Moderate|Low), "
            "management_options (list of strings — options for the clinician to consider, not orders), "
            "recommended_first_step (string — a suggestion, not a directive), "
            "further_investigations_if_needed (list of strings), "
            "clinical_advisory_note (string — must explicitly state that the clinician retains "
            "full decision authority over patient management)."
        )
        input_block = json.dumps({**base_input, "investigation_results": extra})

    else:
        raise ValueError(
            f"Unknown reasoning_type: {reasoning_type!r}. "
            "Valid values: 'initial_with_followup', 'test_recommendation', 'advisory_conclusion'."
        )

    return (
        f"### System:\n{SYSTEM_PROMPT}\n\n"
        f"### Instruction:\n{instruction}\n\n"
        f"### Input:\n{input_block}\n\n"
        f"### Response:\n"
    )


def resolve_runner(llama_cli: str) -> str:
    """
    Return the llama.cpp binary that performs one-shot (non-chat) completion.

    Newer llama.cpp builds turned `llama-cli` into a conversation-only front end —
    given `-p` it waits for interactive turns instead of completing the prompt and
    exiting, which hangs Aletheia until the timeout. Those builds ship the one-shot
    completer as a separate `llama-completion` binary, so prefer it when present and
    fall back to the configured `llama-cli` on older builds.
    """
    configured = Path(llama_cli)
    completion = configured.with_name("llama-completion")
    return str(completion) if completion.exists() else str(configured)


# Trailing markers llama.cpp appends to stdout after generation finishes.
_END_MARKERS = ("> EOF by user", "[end of text]")


def _clean_output(stdout: str) -> str:
    """Strip llama.cpp's end-of-generation markers from captured stdout."""
    text = stdout
    for marker in _END_MARKERS:
        idx = text.rfind(marker)
        if idx != -1:
            text = text[:idx]
    return text.strip()


def _inference_command(prompt: str) -> list[str]:
    """Validate the install and build the llama.cpp command line for one prompt."""
    cfg = load_config()
    llama_bin = cfg["llama_cli"]
    model_path = cfg["model_path"]

    if not Path(llama_bin).exists():
        raise FileNotFoundError(
            f"llama-cli not found at {llama_bin}\nRun: bash setup_venv.sh"
        )
    if not Path(model_path).exists():
        raise FileNotFoundError(
            f"Model not found at {model_path}\nRun model download first."
        )

    # `--log-disable` is deliberately not passed: on current llama.cpp it silences the
    # generated tokens along with the logs, leaving stdout empty. Logs go to stderr,
    # which is captured on a separate pipe, so stdout stays clean without it.
    return [
        resolve_runner(llama_bin),
        "-m", model_path,
        "-p", prompt,
        "-n", str(cfg.get("max_tokens", 512)),
        "-c", str(cfg.get("context_size", 1024)),
        "-t", str(cfg.get("threads", 4)),
        "--temp", str(cfg.get("temperature", 0.1)),
        "--no-display-prompt",
        "-ngl", "0",
    ]


# llama.cpp reports its own timings on stderr, e.g.
#   llama_perf_context_print: eval time = 21538.19 ms / 122 runs ( 5.67 tokens per second)
# There are usually two such lines — prompt evaluation first, then generation —
# and the generation rate is the one a reader cares about, so we take the last.
_PERF_RATE = re.compile(r"([\d.]+)\s+tokens per second")
_PERF_RUNS = re.compile(r"/\s*(\d+)\s+runs")


def _parse_perf(stderr: str) -> dict:
    """Pull the measured generation rate out of llama.cpp's own timing report.

    Measured, not estimated: the console shows a rough live rate while tokens
    are arriving, then replaces it with this number, so the figure that ends up
    on screen next to a throughput claim is llama.cpp's, not ours.
    """
    rates = _PERF_RATE.findall(stderr)
    runs = _PERF_RUNS.findall(stderr)
    return {
        "tokens": int(runs[-1]) if runs else 0,
        "tokens_per_second": float(rates[-1]) if rates else 0.0,
        "measured": bool(rates),
    }


def _split_emittable(buf: str) -> tuple[str, str, bool]:
    """Split the live-preview buffer into (show now, hold back, generation ended).

    Two things must never reach the reader: a complete end marker, and the
    first characters of one that has only partly arrived. So anything from a
    complete marker onward is dropped and the stream is marked finished, and
    otherwise the longest suffix that could still grow into a marker is held
    back until the next read decides what it was.
    """
    for marker in _END_MARKERS:
        idx = buf.find(marker)
        if idx != -1:
            return buf[:idx], "", True

    hold = 0
    for marker in _END_MARKERS:
        for n in range(min(len(marker) - 1, len(buf)), 0, -1):
            if buf.endswith(marker[:n]):
                hold = max(hold, n)
                break
    if not hold:
        return buf, "", False
    return buf[: len(buf) - hold], buf[len(buf) - hold :], False


def stream_inference(prompt: str, timeout: int = 600) -> Iterator[tuple[str, object]]:
    """Run inference and yield output as llama.cpp produces it.

    Yields ``("token", text)`` for each piece of generated text, then exactly one
    ``("done", stats)`` at the end, where stats carries the cleaned text, the
    wall-clock seconds, and llama.cpp's own measured generation rate.

    A stage takes 40 to 60 seconds on an i5-class CPU. Waiting for the whole
    subprocess to exit before showing anything makes that minute look like a
    hang, which is the single worst thing about a slow local model, so the
    front end consumes this generator and paints tokens as they arrive. The
    text yielded here is a live preview: the authoritative output is the
    cleaned string in the final ``done`` payload.
    """
    cmd = _inference_command(prompt)
    t0 = time.time()

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        bufsize=0,
    )

    # subprocess.run() enforced the timeout for us; Popen does not, so a timer
    # kills the process and the flag tells us afterwards why it died.
    timed_out = threading.Event()

    def _expire() -> None:
        timed_out.set()
        if proc.poll() is None:
            proc.kill()

    killer = threading.Timer(timeout, _expire)
    killer.daemon = True
    killer.start()

    # llama.cpp writes its load and timing logs to stderr and blocks once that
    # pipe fills, so it has to be drained while we read stdout.
    stderr_buf: list[bytes] = []
    drainer = threading.Thread(
        target=lambda: stderr_buf.append(proc.stderr.read() or b""), daemon=True
    )
    drainer.start()

    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    raw = ""
    held = ""
    ended = False
    fd = proc.stdout.fileno()

    try:
        while True:
            try:
                # os.read returns as soon as any bytes are available; a plain
                # .read(n) would block until n bytes arrive and stall the stream.
                data = os.read(fd, 512)
            except OSError:
                break
            if not data:
                break
            text = decoder.decode(data)
            if not text:
                continue
            raw += text
            # Keep reading to EOF after the end marker so the child can exit,
            # but show the reader nothing more.
            if ended:
                continue
            held += text
            emit, held, ended = _split_emittable(held)
            if emit:
                yield "token", emit

        tail = decoder.decode(b"", final=True)
        raw += tail
        if not ended:
            emit, _, _ = _split_emittable(held + tail)
            if emit:
                yield "token", emit

        proc.wait()
        elapsed = round(time.time() - t0, 1)

        drainer.join(timeout=2)
        stderr = (stderr_buf[0] if stderr_buf else b"").decode("utf-8", "replace")

        if timed_out.is_set():
            raise TimeoutError(f"Inference exceeded {timeout}s and was stopped.")
        if proc.returncode != 0:
            raise RuntimeError(
                f"llama-cli failed (exit {proc.returncode})\nSTDERR: {stderr[-500:]}"
            )

        stats = {"text": _clean_output(raw), "elapsed": elapsed}
        stats.update(_parse_perf(stderr))
        yield "done", stats
    finally:
        # Covers the ordinary exit and the case where the caller stops consuming
        # because the browser went away — llama.cpp must not be left running on
        # every core of an 8 GB laptop.
        killer.cancel()
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        proc.stdout.close()
        proc.stderr.close()


def run_inference(prompt: str, timeout: int = 600) -> tuple[str, float]:
    """Run inference via llama.cpp CLI. Returns (response_text, elapsed_seconds).

    A thin drain of stream_inference() so the blocking callers (run.py, cli.py)
    and the streaming console share one code path.
    """
    for kind, payload in stream_inference(prompt, timeout=timeout):
        if kind == "done":
            return payload["text"], payload["elapsed"]  # type: ignore[index]
    raise RuntimeError("Inference produced no output.")


def runtime_info() -> dict:
    """Describe the local runtime, for the console's status rail.

    Reads the filesystem only. Aletheia claims to run offline on this machine
    and nothing else; this is the evidence for that claim, shown on screen
    rather than asserted in a banner.
    """
    cfg = load_config()
    model = Path(cfg["model_path"])
    runner = Path(resolve_runner(cfg["llama_cli"]))
    exists = model.exists()
    return {
        "model_name": model.name,
        "model_present": exists,
        "model_size_mb": round(model.stat().st_size / 1e6) if exists else 0,
        "runner": runner.name,
        "runner_present": runner.exists(),
        "threads": cfg.get("threads", os.cpu_count() or 4),
        "context_size": cfg.get("context_size", 1024),
        "max_tokens": cfg.get("max_tokens", 512),
        "gpu_layers": 0,
    }


def parse_response(raw: str) -> dict:
    """Extract and parse JSON from model output."""
    try:
        return json.loads(raw)
    except Exception:
        pass
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return {"raw_response": raw}


def diagnose(
    symptoms: list[str],
    duration_days: int,
    age_group: str = "adult",
    sex: str = "unknown",
    reasoning_type: str = "initial_with_followup",
    extra: str = "",
    timeout: int = 600,
) -> dict:
    """
    Run one stage of the clinical pipeline.

    reasoning_type:
        'initial_with_followup'  — Stage 1: tentative differential + follow-up questions
        'test_recommendation'    — Stage 2: priority tests (extra = follow-up answers)
        'advisory_conclusion'    — Stage 3: management advisory (extra = investigation results)

    Raises HazardRefusal before any prompt is built if the input asks for
    something Aletheia will not supply (see inference/safety.py).
    """
    refusal = screen(", ".join(symptoms), extra)
    if refusal is not None:
        raise HazardRefusal(refusal)

    prompt = build_prompt(symptoms, duration_days, age_group, sex, reasoning_type, extra)
    raw, elapsed = run_inference(prompt, timeout=timeout)
    parsed = parse_response(raw)
    return {
        "response": parsed,
        "raw": raw,
        "elapsed_seconds": elapsed,
        "symptoms": symptoms,
        "duration_days": duration_days,
        "reasoning_type": reasoning_type,
    }


if __name__ == "__main__":
    result = diagnose(
        symptoms=["fever", "headache", "neck stiffness"],
        duration_days=2,
    )
    print(json.dumps(result, indent=2))
