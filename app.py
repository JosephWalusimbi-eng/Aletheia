#!/usr/bin/env python3
"""
app.py
======
Aletheia — Web UI (Gradio)
Multi-step clinical decision support flow:
  Step 1: Enter symptoms → Differential Diagnosis
  Step 2: Answer follow-up questions → Refined Differential
  Step 3: Get investigation recommendations
  Step 4: Enter test results → Final conclusion

Usage:
    source venv/bin/activate
    python3 app.py
    # Opens at http://localhost:7860
"""

import sys
import json
import re
import subprocess
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    import gradio as gr
except ImportError:
    print("Installing gradio...")
    import subprocess as sp
    sp.run([sys.executable, "-m", "pip", "install", "gradio", "-q"], check=True)
    import gradio as gr

from inference.aletheia import build_prompt, load_config, CONFIG

# ── CSS ───────────────────────────────────────────────────────
CSS = """
.aletheia-header {
    background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
    color: white;
    padding: 20px 28px;
    border-radius: 12px;
    margin-bottom: 12px;
}
.aletheia-header h1 { font-size: 1.8rem; font-weight: 700; margin: 0; color: #00d4ff; }
.aletheia-header p  { margin: 4px 0 0; color: #aad4e0; font-size: 0.9rem; }
.offline-badge {
    background: #d4edda; border: 1px solid #28a745; color: #155724;
    padding: 3px 10px; border-radius: 20px; font-size: 0.78rem;
    font-weight: 600; display: inline-block; margin-top: 6px;
}
.disclaimer {
    background: #fff3cd; border-left: 4px solid #ffc107;
    padding: 8px 14px; border-radius: 6px;
    font-size: 0.85rem; color: #856404; margin-bottom: 10px;
}
.step-badge {
    background: #0f2027; color: #00d4ff;
    padding: 4px 12px; border-radius: 12px;
    font-size: 0.8rem; font-weight: 700;
    display: inline-block; margin-bottom: 8px;
}
"""

# ── Run inference directly ────────────────────────────────────
def run_llama(prompt: str, timeout: int = 600) -> tuple[str, float]:
    """Run llama-cli and return (output, elapsed_seconds)."""
    cfg = load_config()
    llama_bin = cfg["llama_cli"]
    model_path = cfg["model_path"]

    print(f"[DEBUG] llama_bin: {llama_bin}")
    print(f"[DEBUG] model_path: {model_path}")
    print(f"[DEBUG] llama exists: {Path(llama_bin).exists()}")
    print(f"[DEBUG] model exists: {Path(model_path).exists()}")

    if not Path(llama_bin).exists():
        raise FileNotFoundError(f"llama-cli not found: {llama_bin}\nRun: bash setup_venv.sh")
    if not Path(model_path).exists():
        raise FileNotFoundError(f"Model not found: {model_path}\nRun model download first.")

    cmd = [
        llama_bin,
        "-m", model_path,
        "-p", prompt,
        "-n", str(cfg.get("max_tokens", 512)),
        "-c", str(cfg.get("context_size", 1024)),
        "-t", str(cfg.get("threads", 4)),
        "--temp", str(cfg.get("temperature", 0.1)),
        "--no-display-prompt",
        "-ngl", "0",
        "--log-disable",
    ]
    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"[DEBUG] returncode: {result.returncode}")
        print(f"[DEBUG] stderr: {result.stderr[-300:]}")
        raise RuntimeError(f"llama-cli error:\n{result.stderr[-300:]}")
    print(f"[DEBUG] stdout length: {len(result.stdout)}")
    print(f"[DEBUG] stdout preview: {result.stdout[:200]}")
    return result.stdout.strip(), round(elapsed, 1)

def parse_json(raw: str) -> dict:
    """Extract and parse JSON from model output."""
    # Try full parse first
    try:
        return json.loads(raw)
    except Exception:
        pass
    # Try to find JSON block
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return {}

def format_differentials(data: dict, elapsed: float) -> str:
    """Format differential diagnosis as markdown table."""
    diffs = (data.get("ranked_differentials") or
             data.get("differentials") or
             data.get("differential_diagnosis") or [])

    if not diffs:
        return f"*No structured output parsed. Raw response shown below.*\n\n```\n{str(data)[:500]}\n```"

    md = f"*Response time: {elapsed}s*\n\n"
    md += "| # | Condition | Probability | Severity |\n"
    md += "|---|-----------|-------------|----------|\n"

    severity_icon = {"Critical": "🔴", "High": "🟠", "Moderate": "🟡", "Low": "🟢"}

    for i, d in enumerate(diffs, 1):
        cond = d.get("condition", "")
        prob = d.get("probability", 0)
        sev  = d.get("severity", "")
        icon = severity_icon.get(sev, "⚪")
        bar  = "█" * int(prob * 10) + "░" * (10 - int(prob * 10))
        md  += f"| **{i}** | {cond} | {prob*100:.0f}% `{bar}` | {icon} {sev} |\n"

    return md

def format_tests(data: dict) -> str:
    """Format investigation recommendations."""
    tests = (data.get("priority_tests") or
             data.get("recommended_tests") or
             data.get("additional_tests") or
             data.get("priority_investigations") or
             data.get("investigations") or [])

    if not tests:
        return "*No investigations in this response.*"

    return "\n".join(f"{i}. {t}" for i, t in enumerate(tests, 1))

def format_followup(data: dict) -> str:
    """Format follow-up questions."""
    fup = (data.get("follow_up_questions") or
           data.get("follow_up") or
           data.get("questions") or [])

    if not fup:
        return "*No follow-up questions generated.*"

    md = "Answer these questions to refine the differential:\n\n"
    for i, q in enumerate(fup, 1):
        md += f"**{i}.** {q}\n\n"
    return md

def format_rationale(data: dict) -> str:
    """Format clinical rationale."""
    r = (data.get("clinical_rationale") or
         data.get("reasoning") or
         data.get("rationale") or "")
    return r if r else "*No rationale in this response.*"

def format_redflags(data: dict) -> str:
    """Format red flags."""
    rf = data.get("red_flags") or []
    if not rf:
        return "*No red flags identified.*"
    return "\n".join(f"⚠️  {f}" for f in rf)

# ── Step 1: Initial differential ─────────────────────────────
def step1_diagnose(symptoms_text, duration, age_group, sex):
    if not symptoms_text.strip():
        return "*Please enter at least one symptom.*", "", "", "", ""

    symptoms = [s.strip().lower() for s in symptoms_text.split(",") if s.strip()]
    prompt = build_prompt(symptoms, int(duration), age_group, sex, "initial_differential")

    try:
        raw, elapsed = run_llama(prompt)
        data = parse_json(raw)
        diff_md  = format_differentials(data, elapsed)
        tests_md = format_tests(data)
        rat_md   = format_rationale(data)
        rf_md    = format_redflags(data)
        fup_md   = format_followup(data)
        return diff_md, fup_md, tests_md, rat_md, rf_md
    except Exception as e:
        return f"**Error:** {e}", "", "", "", ""

# ── Step 2: Refined differential after follow-up answers ──────
def step2_refine(symptoms_text, duration, age_group, sex, followup_answers):
    if not followup_answers.strip():
        return "*Please enter your answers to the follow-up questions.*", "", ""

    symptoms = [s.strip().lower() for s in symptoms_text.split(",") if s.strip()]

    # Build evidence update prompt
    prompt = (
        f"### System:\nYou are Aletheia, an offline-first clinical decision support AI "
        f"designed for district hospitals and health centres in sub-Saharan Africa. "
        f"Always respond in structured JSON format.\n\n"
        f"### Instruction:\nUpdate the differential diagnosis based on new clinical information. "
        f"Revise probability estimates and recommend priority investigations.\n\n"
        f"### Input:\n"
        + json.dumps({
            "symptoms": symptoms,
            "duration_days": int(duration),
            "patient_age_group": age_group,
            "sex": sex,
            "additional_history": followup_answers,
        }) +
        f"\n\n### Response:\n"
    )

    try:
        raw, elapsed = run_llama(prompt)
        data = parse_json(raw)
        diff_md  = format_differentials(data, elapsed)
        tests_md = format_tests(data)
        rat_md   = format_rationale(data)
        return diff_md, tests_md, rat_md
    except Exception as e:
        return f"**Error:** {e}", "", ""

# ── Step 3: Final conclusion after test results ───────────────
def step3_conclude(symptoms_text, duration, age_group, sex, test_results):
    if not test_results.strip():
        return "*Please enter your investigation results.*", ""

    symptoms = [s.strip().lower() for s in symptoms_text.split(",") if s.strip()]

    prompt = (
        f"### System:\nYou are Aletheia, an offline-first clinical decision support AI. "
        f"Always respond in structured JSON format.\n\n"
        f"### Instruction:\nGiven investigation results, provide a final diagnosis, "
        f"immediate management plan, and any additional steps required.\n\n"
        f"### Input:\n"
        + json.dumps({
            "symptoms": symptoms,
            "duration_days": int(duration),
            "patient_age_group": age_group,
            "sex": sex,
            "investigation_results": test_results,
        }) +
        f"\n\n### Response:\n"
    )

    try:
        raw, elapsed = run_llama(prompt)
        data = parse_json(raw)

        # Format final conclusion
        diagnosis = data.get("final_diagnosis") or data.get("diagnosis") or ""
        management = data.get("management") or data.get("treatment") or data.get("immediate_management") or []
        rationale = format_rationale(data)

        conclusion_md = f"*Response time: {elapsed}s*\n\n"
        if diagnosis:
            conclusion_md += f"### Final Diagnosis\n**{diagnosis}**\n\n"
        if management:
            conclusion_md += "### Immediate Management\n"
            if isinstance(management, list):
                conclusion_md += "\n".join(f"{i}. {m}" for i, m in enumerate(management, 1))
            else:
                conclusion_md += str(management)
        if not diagnosis and not management:
            conclusion_md += f"```json\n{raw[:800]}\n```"

        return conclusion_md, rationale
    except Exception as e:
        return f"**Error:** {e}", ""

# ── Build UI ──────────────────────────────────────────────────
def build_ui():
    with gr.Blocks(
        css=CSS,
        title="Aletheia — Clinical Decision Support",
        theme=gr.themes.Soft(primary_hue="cyan", secondary_hue="slate"),
    ) as demo:

        # Header
        gr.HTML("""
        <div class="aletheia-header">
            <h1>⚕ Aletheia Diagnostic AI</h1>
            <p>Offline-first clinical decision support · Soroti University, Uganda · Arapai Technologies International Limited</p>
            <span class="offline-badge">🔒 Fully Offline — No Internet Required</span>
        </div>
        <div class="disclaimer">
            <strong>⚠ Clinical Disclaimer:</strong> Aletheia is a research prototype and decision support tool.
            It does not replace clinical judgement. All outputs must be reviewed by a qualified healthcare
            professional. Not a licensed medical device.
        </div>
        """)

        # ── Shared patient inputs ─────────────────────────────
        with gr.Row():
            with gr.Column(scale=1):
                gr.HTML('<span class="step-badge">PATIENT PRESENTATION</span>')
                symptoms_input = gr.Textbox(
                    label="Symptoms",
                    placeholder="fever, headache, neck stiffness, vomiting",
                    info="Enter symptoms separated by commas",
                    lines=3,
                )
                with gr.Row():
                    duration_input = gr.Slider(label="Duration (days)", minimum=0, maximum=365, value=2, step=1)
                with gr.Row():
                    age_input = gr.Dropdown(
                        label="Age Group",
                        choices=["neonate","infant","child","adolescent","adult","elderly"],
                        value="adult",
                    )
                    sex_input = gr.Dropdown(
                        label="Sex",
                        choices=["unknown","male","female"],
                        value="unknown",
                    )

        # ── STEP 1 ────────────────────────────────────────────
        gr.HTML('<hr><span class="step-badge">STEP 1 — Initial Differential Diagnosis</span>')
        step1_btn = gr.Button("▶  Run Initial Assessment", variant="primary", size="lg")

        with gr.Row():
            with gr.Column(scale=1):
                step1_diff = gr.Markdown("*Enter symptoms above and click Run.*", label="Ranked Differentials")
                step1_rf   = gr.Markdown(label="⚠️ Red Flags")
            with gr.Column(scale=1):
                step1_rat  = gr.Markdown(label="📋 Clinical Rationale")

        # ── STEP 2 ────────────────────────────────────────────
        gr.HTML('<hr><span class="step-badge">STEP 2 — Answer Follow-up Questions</span>')
        gr.Markdown("*After Step 1, Aletheia will suggest follow-up questions. Enter your answers below to refine the differential.*")

        step1_fup = gr.Markdown(label="Follow-up Questions from Step 1")

        followup_answers = gr.Textbox(
            label="Your Answers",
            placeholder="e.g. Kernig sign positive, no rash, last travel 2 weeks ago, vaccinated...",
            lines=3,
            info="Answer the follow-up questions above to help Aletheia refine the diagnosis"
        )
        step2_btn = gr.Button("▶  Refine Differential", variant="primary")

        with gr.Row():
            step2_diff  = gr.Markdown(label="🩺 Refined Differential")
            step2_tests = gr.Markdown(label="🔬 Priority Investigations")
        step2_rat = gr.Markdown(label="📋 Updated Rationale")

        # ── STEP 3 ────────────────────────────────────────────
        gr.HTML('<hr><span class="step-badge">STEP 3 — Enter Investigation Results</span>')
        gr.Markdown("*After running investigations from Step 2, enter the results below for a final conclusion.*")

        test_results_input = gr.Textbox(
            label="Investigation Results",
            placeholder="e.g. CSF: cloudy, WBC 2000, protein high, glucose low. Malaria RDT: negative. Blood culture: pending...",
            lines=4,
            info="Enter results of investigations recommended in Step 2"
        )
        step3_btn = gr.Button("▶  Get Final Conclusion", variant="primary")

        with gr.Row():
            step3_conclusion = gr.Markdown(label="✅ Final Diagnosis & Management")
            step3_rat        = gr.Markdown(label="📋 Final Rationale")

        # ── Example cases ─────────────────────────────────────
        gr.HTML('<hr>')
        gr.Markdown("### Example Cases — Click to load")
        gr.Examples(
            examples=[
                ["fever, headache, neck stiffness, vomiting",           2,  "adult",     "unknown"],
                ["altered consciousness, seizures, fever, pallor",       2,  "child",     "female"],
                ["cough, weight loss, night sweats, haemoptysis",       30,  "adult",     "male"],
                ["seizures, severe headache, high blood pressure, oedema", 1, "adult",    "female"],
                ["heavy bleeding after delivery, pallor, tachycardia",   0,  "adult",    "female"],
                ["chest pain, sweating, left arm pain",                  1,  "elderly",  "male"],
                ["severe wasting, oedema, anorexia",                    90,  "child",    "unknown"],
                ["bite wound, local swelling, ptosis",                   0,  "adult",    "male"],
            ],
            inputs=[symptoms_input, duration_input, age_input, sex_input],
            label="Click any case to load it",
        )

        # Footer
        gr.HTML("""
        <hr style="margin-top:24px; border-color:#dee2e6;">
        <div style="text-align:center; color:#6c757d; font-size:0.82rem; padding:12px;">
            <strong>Aletheia</strong> · Soroti University, Uganda · ADTC 2026 ·
            <a href="https://github.com/JosephWalusimbi-eng/Aletheia" target="_blank">GitHub</a>
        </div>
        """)

        # ── Wire up buttons ───────────────────────────────────
        step1_btn.click(
            fn=step1_diagnose,
            inputs=[symptoms_input, duration_input, age_input, sex_input],
            outputs=[step1_diff, step1_fup, step2_tests, step1_rat, step1_rf],
            show_progress="full",
        )

        step2_btn.click(
            fn=step2_refine,
            inputs=[symptoms_input, duration_input, age_input, sex_input, followup_answers],
            outputs=[step2_diff, step2_tests, step2_rat],
            show_progress="full",
        )

        step3_btn.click(
            fn=step3_conclude,
            inputs=[symptoms_input, duration_input, age_input, sex_input, test_results_input],
            outputs=[step3_conclusion, step3_rat],
            show_progress="full",
        )

    return demo

# ── Launch ────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\nAletheia — Starting web interface...")
    print("Open your browser at: http://localhost:7860\n")
    demo = build_ui()
    demo.queue(default_concurrency_limit=1)
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        inbrowser=True,
        show_error=True,
        max_threads=1,
    )
