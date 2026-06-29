#!/usr/bin/env python3
"""
app.py
======
Aletheia — Web UI (Gradio)
Runs in the browser. No internet required after first pip install.

Usage:
    python3 app.py
    # Opens at http://localhost:7860
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    import gradio as gr
except ImportError:
    print("Installing gradio...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "gradio", "-q"], check=True)
    import gradio as gr

from inference.aletheia import diagnose, CONFIG

# ── Constants ─────────────────────────────────────────────────
SEVERITY_EMOJI = {
    "Critical": "🔴",
    "High":     "🟠",
    "Moderate": "🟡",
    "Low":      "🟢",
}

REASONING_TYPES = {
    "Differential Diagnosis":     "initial_differential",
    "Investigation Recommendations": "test_recommendation",
    "Severity & Level of Care":   "severity_assessment",
    "Immediate Management":       "treatment_hint",
    "Follow-up Questions":        "follow_up_questions",
    "Red Flags Only":             "red_flag_identification",
}

AGE_GROUPS = ["neonate", "infant", "child", "adolescent", "adult", "elderly"]

# ── CSS ───────────────────────────────────────────────────────
CSS = """
.aletheia-header {
    background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
    color: white;
    padding: 24px 32px;
    border-radius: 12px;
    margin-bottom: 16px;
}
.aletheia-header h1 {
    font-size: 2rem;
    font-weight: 700;
    margin: 0;
    color: #00d4ff;
}
.aletheia-header p {
    margin: 4px 0 0;
    color: #aad4e0;
    font-size: 0.95rem;
}
.disclaimer {
    background: #fff3cd;
    border-left: 4px solid #ffc107;
    padding: 10px 16px;
    border-radius: 6px;
    font-size: 0.88rem;
    color: #856404;
    margin-bottom: 12px;
}
.offline-badge {
    background: #d4edda;
    border: 1px solid #28a745;
    color: #155724;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
    display: inline-block;
    margin-top: 8px;
}
.result-box {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 16px;
    font-family: monospace;
}
.critical { color: #dc3545; font-weight: bold; }
.high     { color: #fd7e14; font-weight: bold; }
.moderate { color: #ffc107; font-weight: bold; }
.low      { color: #28a745; font-weight: bold; }
"""

# ── Format output ─────────────────────────────────────────────
def format_output(result: dict) -> tuple[str, str, str, str, str]:
    """
    Returns (differentials_md, tests_md, rationale_md, redflags_md, meta_md)
    """
    response = result.get("response", {})
    elapsed = result.get("elapsed_seconds", 0)
    raw = result.get("raw", "")

    # ── Differentials ─────────────────────────────────────────
    diffs = (response.get("ranked_differentials", []) or
             response.get("differentials", []) or
             response.get("differential_diagnosis", []))
    if diffs:
        diff_md = "| Rank | Condition | Probability | Severity |\n"
        diff_md += "|------|-----------|------------|----------|\n"
        for i, d in enumerate(diffs, 1):
            cond = d.get("condition", "")
            prob = d.get("probability", 0)
            sev = d.get("severity", "")
            emoji = SEVERITY_EMOJI.get(sev, "⚪")
            bar = "█" * int(prob * 10) + "░" * (10 - int(prob * 10))
            diff_md += f"| **{i}** | {cond} | {prob*100:.0f}% `{bar}` | {emoji} {sev} |\n"
    else:
        diff_md = raw[:1000] if raw else "No structured output."

    # ── Tests ─────────────────────────────────────────────────
    tests = (response.get("priority_tests", []) +
             response.get("recommended_tests", []) +
             response.get("additional_tests", []) +
             response.get("priority_investigations", []) +
             response.get("investigations", []))
    if tests:
        tests_md = "\n".join(f"{i}. {t}" for i, t in enumerate(tests, 1))
    else:
        tests_md = "_No investigation recommendations in this response._"

    # ── Rationale ─────────────────────────────────────────────
    rationale = (response.get("clinical_rationale", "") or
                 response.get("reasoning", ""))
    rationale_md = rationale if rationale else "_No rationale provided._"

    # ── Red flags ─────────────────────────────────────────────
    red_flags = response.get("red_flags", [])
    if red_flags:
        rf_md = "\n".join(f"⚠️  {rf}" for rf in red_flags)
    else:
        fup = response.get("follow_up_questions", [])
        if fup:
            rf_md = "\n".join(f"❓ {q}" for q in fup)
        else:
            rf_md = "_No red flags or follow-up questions identified._"

    # ── Meta ──────────────────────────────────────────────────
    meta_md = (
        f"**Response time:** {elapsed:.1f}s  \n"
        f"**Model:** {Path(CONFIG['model_path']).name}  \n"
        f"**Mode:** CPU-only (no GPU, no internet)  \n"
        f"**Reasoning task:** {result.get('reasoning_type', 'N/A')}"
    )

    return diff_md, tests_md, rationale_md, rf_md, meta_md

# ── Main inference function ───────────────────────────────────
def run_aletheia(
    symptoms_text: str,
    duration: int,
    age_group: str,
    sex: str,
    reasoning_label: str,
) -> tuple:
    """Gradio callback — runs inference and returns formatted results."""

    if not symptoms_text.strip():
        empty = "_Please enter at least one symptom._"
        return empty, empty, empty, empty, empty

    # Parse symptoms
    symptoms = [s.strip().lower() for s in symptoms_text.split(",") if s.strip()]
    if not symptoms:
        empty = "_Please enter symptoms separated by commas._"
        return empty, empty, empty, empty, empty

    reasoning_type = REASONING_TYPES.get(reasoning_label, "initial_differential")

    try:
        result = diagnose(
            symptoms=symptoms,
            duration_days=int(duration),
            age_group=age_group,
            sex=sex.lower(),
            reasoning_type=reasoning_type,
            timeout=600,
        )
        return format_output(result)

    except FileNotFoundError as e:
        err = f"**Error:** {e}\n\nRun `bash install.sh` and `bash models/download_model.sh` first."
        return err, "", "", "", ""

    except Exception as e:
        err = f"**Inference failed:** {e}"
        return err, "", "", "", ""

# ── Example cases ─────────────────────────────────────────────
EXAMPLES = [
    ["fever, headache, neck stiffness, vomiting",     2,  "adult",      "unknown",  "Differential Diagnosis"],
    ["altered consciousness, seizures, fever, pallor", 2, "child",      "female",   "Differential Diagnosis"],
    ["cough, weight loss, night sweats, haemoptysis", 30, "adult",      "male",     "Investigation Recommendations"],
    ["seizures in pregnancy, severe headache, high BP", 1, "adult",     "female",   "Severity & Level of Care"],
    ["heavy bleeding after delivery, pallor, tachycardia", 0, "adult",  "female",   "Immediate Management"],
    ["chest pain, sweating, left arm pain, nausea",   1,  "elderly",   "male",     "Red Flags Only"],
    ["severe wasting, oedema, anorexia, hair changes", 90, "child",    "unknown",  "Differential Diagnosis"],
    ["bite wound, local swelling, coagulopathy signs", 0,  "adult",    "male",     "Immediate Management"],
]

# ── Build UI ──────────────────────────────────────────────────
def build_ui():
    with gr.Blocks(
        css=CSS,
        title="Aletheia — Clinical Decision Support",
        theme=gr.themes.Soft(
            primary_hue="cyan",
            secondary_hue="slate",
        ),
    ) as demo:

        # Header
        gr.HTML("""
        <div class="aletheia-header">
            <h1>⚕ Aletheia Diagnostic AI</h1>
            <p>Offline-first clinical decision support for sub-Saharan Africa</p>
            <p>Soroti University, Uganda · Arapai Technologies International Limited</p>
            <span class="offline-badge">🔒 Fully Offline — No Internet Required</span>
        </div>
        <div class="disclaimer">
            <strong>⚠ Clinical Disclaimer:</strong> Aletheia is a research prototype and 
            decision support tool. It does not replace clinical judgement. All outputs 
            must be reviewed by a qualified healthcare professional before any clinical 
            action is taken. Not a licensed medical device.
        </div>
        """)

        with gr.Row():
            # ── Left panel — Input ─────────────────────────────
            with gr.Column(scale=1):
                gr.Markdown("### Patient Presentation")

                symptoms_input = gr.Textbox(
                    label="Symptoms",
                    placeholder="fever, headache, neck stiffness, vomiting",
                    info="Enter symptoms separated by commas",
                    lines=3,
                )

                with gr.Row():
                    duration_input = gr.Slider(
                        label="Duration (days)",
                        minimum=0,
                        maximum=365,
                        value=1,
                        step=1,
                    )

                with gr.Row():
                    age_input = gr.Dropdown(
                        label="Age Group",
                        choices=AGE_GROUPS,
                        value="adult",
                    )
                    sex_input = gr.Dropdown(
                        label="Sex",
                        choices=["unknown", "male", "female"],
                        value="unknown",
                    )

                reasoning_input = gr.Dropdown(
                    label="Clinical Reasoning Task",
                    choices=list(REASONING_TYPES.keys()),
                    value="Differential Diagnosis",
                    info="What do you need Aletheia to help with?",
                )

                submit_btn = gr.Button(
                    "▶  Run Clinical Assessment",
                    variant="primary",
                    size="lg",
                )

                gr.Markdown("### Example Cases")
                gr.Examples(
                    examples=EXAMPLES,
                    inputs=[symptoms_input, duration_input, age_input,
                            sex_input, reasoning_input],
                    label="Click any case to load it",
                )

            # ── Right panel — Output ───────────────────────────
            with gr.Column(scale=2):
                gr.Markdown("### Assessment")

                with gr.Tabs():
                    with gr.TabItem("🩺 Differential Diagnosis"):
                        diff_output = gr.Markdown(
                            value="_Enter symptoms and click Run._",
                            label="Ranked Differentials",
                        )

                    with gr.TabItem("🔬 Investigations"):
                        tests_output = gr.Markdown(
                            value="_Enter symptoms and click Run._",
                        )

                    with gr.TabItem("📋 Clinical Rationale"):
                        rationale_output = gr.Markdown(
                            value="_Enter symptoms and click Run._",
                        )

                    with gr.TabItem("⚠️ Red Flags"):
                        rf_output = gr.Markdown(
                            value="_Enter symptoms and click Run._",
                        )

                    with gr.TabItem("ℹ️ Metadata"):
                        meta_output = gr.Markdown(
                            value="_Run an assessment to see metadata._",
                        )

        # Footer
        gr.HTML("""
        <hr style="margin-top:32px; border-color:#dee2e6;">
        <div style="text-align:center; color:#6c757d; font-size:0.85rem; padding:16px;">
            <strong>Aletheia</strong> · Soroti University, Uganda · ADTC 2026 Submission<br>
            Built with Qwen2.5-3B-Instruct + QLoRA + llama.cpp · 
            <a href="https://github.com/JosephWalusimbi-eng/Aletheia" target="_blank">GitHub</a>
        </div>
        """)

        # Wire up
        submit_btn.click(
            fn=run_aletheia,
            inputs=[symptoms_input, duration_input, age_input,
                    sex_input, reasoning_input],
            outputs=[diff_output, tests_output, rationale_output,
                     rf_output, meta_output],
            show_progress="full",
        )

        # Also trigger on Enter in symptoms box
        symptoms_input.submit(
            fn=run_aletheia,
            inputs=[symptoms_input, duration_input, age_input,
                    sex_input, reasoning_input],
            outputs=[diff_output, tests_output, rationale_output,
                     rf_output, meta_output],
        )

    return demo


# ── Launch ────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\nAletheia — Starting web interface...")
    print("Open your browser at: http://localhost:7860\n")

    demo = build_ui()
    demo.queue(
        default_concurrency_limit=1,
    )
    demo.launch(
        server_name="0.0.0.0",   # accessible on local network
        server_port=7860,
        share=False,              # no internet tunnel — stays fully offline
        inbrowser=True,           # auto-open browser
        show_error=True,
        max_threads=1,
    )
