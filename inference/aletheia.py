"""
aletheia.py
===========
Core inference wrapper for Aletheia Diagnostic AI.
Three-stage clinical pipeline:
  Stage 1 (initial_with_followup)  — tentative differential + follow-up questions to ask the clinician
  Stage 2 (test_recommendation)    — priority investigations after follow-up answers (headline output)
  Stage 3 (advisory_conclusion)    — management advisory after test results (doctor decides)
"""

import subprocess
import json
import os
import re
import time
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {
        "llama_cli": str(Path.home() / "llama.cpp/build/bin/llama-cli"),
        "model_path": str(Path(__file__).parent.parent / "models/aletheia_q4km.gguf"),
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


def run_inference(prompt: str, timeout: int = 600) -> tuple[str, float]:
    """Run inference via llama.cpp CLI. Returns (response_text, elapsed_seconds)."""
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
    cmd = [
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

    t0 = time.time()
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL
    )
    elapsed = round(time.time() - t0, 1)

    if result.returncode != 0:
        raise RuntimeError(
            f"llama-cli failed (exit {result.returncode})\n"
            f"STDERR: {result.stderr[-500:]}"
        )

    return _clean_output(result.stdout), elapsed


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
    """
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
