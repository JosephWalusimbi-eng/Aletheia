"""
aletheia.py
===========
Core inference wrapper for Aletheia Diagnostic AI.
Calls llama.cpp CLI with the GGUF model and parses structured output.
"""

import subprocess
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

# ── Load config ───────────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent / "config.json"

def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    # Fallback defaults
    return {
        "llama_cli": str(Path.home() / "llama.cpp/build/bin/llama-cli"),
        "model_path": str(Path(__file__).parent.parent / "models/aletheia_q4km.gguf"),
        "context_size": 1024,
        "threads": os.cpu_count() or 4,
        "max_tokens": 512,
        "temperature": 0.1,
    }

CONFIG = load_config()

# ── Prompt builder ────────────────────────────────────────────
SYSTEM_PROMPT = """You are Aletheia, an offline-first clinical decision support AI 
designed for district hospitals and health centres in sub-Saharan Africa. 
You provide ranked differential diagnoses, investigation recommendations, 
and clinical reasoning for presentations common in East and Central Africa.
Always respond in structured JSON format."""

def build_prompt(
    symptoms: list[str],
    duration_days: int,
    age_group: str = "adult",
    sex: str = "unknown",
    reasoning_type: str = "initial_differential",
) -> str:
    """Build a structured clinical prompt."""

    instructions = {
        "initial_differential": (
            "Analyze the patient presentation and provide a ranked differential "
            "diagnosis with probability estimates and severity ratings. "
            "Prioritize conditions prevalent in sub-Saharan Africa."
        ),
        "test_recommendation": (
            "Recommend the most appropriate diagnostic tests in priority order, "
            "considering what is available at a district hospital in Uganda."
        ),
        "severity_assessment": (
            "Assess the severity of this presentation and determine the appropriate "
            "level of care. Identify any immediate life threats and red flags."
        ),
        "treatment_hint": (
            "Outline the immediate management approach appropriate for a "
            "resource-limited district hospital. Include first-line treatments."
        ),
        "follow_up_questions": (
            "What targeted follow-up questions should the clinician ask to refine "
            "the differential diagnosis and assess severity?"
        ),
        "red_flag_identification": (
            "Identify the red flag signs and symptoms in this presentation that "
            "require immediate escalation or emergency intervention."
        ),
    }

    instruction = instructions.get(reasoning_type, instructions["initial_differential"])

    clinical_input = json.dumps({
        "symptoms": symptoms,
        "duration_days": duration_days,
        "patient_age_group": age_group,
        "sex": sex,
    })

    return (
        f"### System:\n{SYSTEM_PROMPT}\n\n"
        f"### Instruction:\n{instruction}\n\n"
        f"### Input:\n{clinical_input}\n\n"
        f"### Response:\n"
    )

# ── Inference ─────────────────────────────────────────────────
def run_inference(
    prompt: str,
    timeout: int = 120,
) -> tuple[str, float]:
    """
    Run inference via llama.cpp CLI.
    Returns (response_text, elapsed_seconds).
    """
    llama_bin = CONFIG["llama_cli"]
    model_path = CONFIG["model_path"]

    if not Path(llama_bin).exists():
        raise FileNotFoundError(
            f"llama-cli not found at {llama_bin}\n"
            "Run: bash install.sh"
        )

    if not Path(model_path).exists():
        raise FileNotFoundError(
            f"Model not found at {model_path}\n"
            "Run: bash models/download_model.sh"
        )

    cmd = [
        llama_bin,
        "-m", model_path,
        "-p", prompt,
        "-n", str(CONFIG["max_tokens"]),
        "-c", str(CONFIG["context_size"]),
        "-t", str(CONFIG["threads"]),
        "--temp", str(CONFIG["temperature"]),
        "--no-display-prompt",
        "-ngl", "0",      # CPU only — no GPU layers
        "--log-disable",
    ]

    t0 = time.time()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    elapsed = time.time() - t0

    if result.returncode != 0:
        raise RuntimeError(
            f"llama-cli failed (exit {result.returncode})\n"
            f"STDERR: {result.stderr[-500:]}"
        )

    return result.stdout.strip(), elapsed

# ── Parse response ────────────────────────────────────────────
def parse_response(raw: str) -> dict:
    """
    Try to parse structured JSON from model output.
    Falls back to returning raw text if parsing fails.
    """
    # Try to extract JSON block
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # Return raw as fallback
    return {"raw_response": raw}

# ── Main API function ─────────────────────────────────────────
def diagnose(
    symptoms: list[str],
    duration_days: int,
    age_group: str = "adult",
    sex: str = "unknown",
    reasoning_type: str = "initial_differential",
    timeout: int = 180,
) -> dict:
    """
    Main diagnosis function.

    Parameters
    ----------
    symptoms      : list of symptom strings
    duration_days : how long symptoms have been present
    age_group     : neonate / infant / child / adolescent / adult / elderly
    sex           : male / female / unknown
    reasoning_type: initial_differential / test_recommendation /
                    severity_assessment / treatment_hint /
                    follow_up_questions / red_flag_identification
    timeout       : max seconds to wait for response

    Returns
    -------
    dict with parsed response and metadata
    """
    prompt = build_prompt(symptoms, duration_days, age_group, sex, reasoning_type)
    raw, elapsed = run_inference(prompt, timeout=timeout)
    parsed = parse_response(raw)

    return {
        "response": parsed,
        "raw": raw,
        "elapsed_seconds": round(elapsed, 2),
        "symptoms": symptoms,
        "duration_days": duration_days,
        "reasoning_type": reasoning_type,
    }


if __name__ == "__main__":
    # Quick test
    result = diagnose(
        symptoms=["fever", "headache", "neck stiffness"],
        duration_days=2,
    )
    print(json.dumps(result, indent=2))
