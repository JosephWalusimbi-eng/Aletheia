#!/usr/bin/env python3
"""
app.py
======
Aletheia — Web UI (Gradio)
Three-stage clinical decision support pipeline:
  Stage 1: Enter symptoms → Follow-up Questions (primary) + Tentative Differential (secondary)
  Stage 2: Answer follow-up questions → Recommended Investigations (primary) + Working Differential
  Stage 3: Enter investigation results → Clinical Advisory (doctor retains all decision authority)

Stage 2 button is disabled until Stage 1 succeeds.
Stage 3 button is disabled until Stage 2 succeeds.
"""

import os
import sys
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import gradio as gr
except ImportError:
    import subprocess as sp
    sp.run([sys.executable, "-m", "pip", "install", "gradio", "-q"], check=True)
    import gradio as gr

from inference.aletheia import build_prompt, run_inference

CSS = """
.aletheia-header {
    background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
    color: white; padding: 20px 28px; border-radius: 12px; margin-bottom: 12px;
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
    padding: 8px 14px; border-radius: 6px; font-size: 0.85rem;
    color: #856404; margin-bottom: 10px;
}
.step-badge {
    background: #0f2027; color: #00d4ff; padding: 4px 12px;
    border-radius: 12px; font-size: 0.8rem; font-weight: 700;
    display: inline-block; margin-bottom: 8px;
}
.action-box {
    background: #e8f4f8; border: 1px solid #17a2b8; border-radius: 8px;
    padding: 12px 18px; margin: 16px 0; font-size: 0.9rem; color: #0c5460;
}
"""

# ── Run inference ─────────────────────────────────────────────
def run_llama(prompt: str, timeout: int = 600) -> tuple[str, float]:
    """Delegate to the shared wrapper so the UI and the CLIs invoke llama.cpp identically."""
    return run_inference(prompt, timeout=timeout)


def parse_json(raw: str) -> dict:
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
    return {}


# ── Formatters ────────────────────────────────────────────────
def fmt_followup_questions(data: dict) -> str:
    fup = (data.get("follow_up_questions") or
           data.get("follow_up") or
           data.get("questions") or [])
    if not fup:
        return "*No follow-up questions generated — check model output.*"
    md = "**Answer these questions, then click Run Step 2:**\n\n"
    for i, q in enumerate(fup, 1):
        md += f"**{i}.** {q}\n\n"
    return md


def fmt_tentative_differential(data: dict, elapsed: float) -> str:
    diffs = (data.get("tentative_differentials") or
             data.get("ranked_differentials") or
             data.get("differentials") or
             data.get("differential_diagnosis") or [])
    if not diffs:
        return "*No tentative differential generated.*"
    md = f"*{elapsed}s — Tentative only. Do not act on this before tests are performed.*\n\n"
    md += "| Condition | Probability | Severity |\n|-----------|-------------|----------|\n"
    for d in diffs:
        cond = d.get("condition", "")
        prob = d.get("probability", 0)
        sev  = d.get("severity", "")
        md  += f"| {cond} | {prob*100:.0f}% | {sev} |\n"
    return md


def fmt_redflags(data: dict) -> str:
    rf = data.get("red_flags") or []
    if not rf:
        return "*No red flags identified.*"
    return "\n".join(f"⚠️  {f}" for f in rf)


def fmt_rationale(data: dict) -> str:
    r = (data.get("clinical_rationale") or
         data.get("rationale_for_tests") or
         data.get("reasoning") or "")
    return r if r else "*No rationale in this response.*"


def fmt_recommended_tests(data: dict, elapsed: float) -> str:
    tests = (data.get("recommended_tests") or
             data.get("priority_tests") or
             data.get("investigations") or [])
    if not tests:
        return "*No test recommendations generated — check model output.*"
    md = f"*{elapsed}s*\n\n**Perform these investigations before entering results in Step 3:**\n\n"
    for i, t in enumerate(tests, 1):
        md += f"{i}. {t}\n"
    return md


def fmt_working_differential(data: dict) -> str:
    diffs = (data.get("working_differential") or
             data.get("tentative_differentials") or
             data.get("ranked_differentials") or
             data.get("differentials") or [])
    if not diffs:
        return "*No working differential provided.*"
    md = "*Context — guides test selection, not a confirmed diagnosis:*\n\n"
    for i, d in enumerate(diffs, 1):
        cond = d.get("condition", "")
        prob = d.get("probability", 0)
        md  += f"{i}. {cond} ({prob*100:.0f}%)\n"
    return md


ADVISORY_HEADER = (
    "> **CLINICAL ADVISORY — Decision Authority: Treating Clinician**\n\n"
    "> This output is decision support only. The treating clinician "
    "makes all final patient management decisions.\n\n"
    "---\n\n"
)


def fmt_advisory(data: dict, elapsed: float) -> str:
    diagnosis  = (data.get("likely_diagnosis") or
                  data.get("final_diagnosis") or
                  data.get("diagnosis") or "")
    confidence = data.get("diagnostic_confidence") or ""
    options    = (data.get("management_options") or
                  data.get("management") or
                  data.get("treatment") or [])
    first_step = data.get("recommended_first_step") or ""
    further    = data.get("further_investigations_if_needed") or []
    advisory   = data.get("clinical_advisory_note") or ""

    if not any([diagnosis, options, first_step]):
        return f"*{elapsed}s*\n\n```\n{str(data)[:800]}\n```"

    md = f"*{elapsed}s*\n\n" + ADVISORY_HEADER

    if diagnosis:
        conf_str = f" *(confidence: {confidence})*" if confidence else ""
        md += f"### Likely Diagnosis\n{diagnosis}{conf_str}\n\n"

    if options:
        md += "### Management Options for Clinician's Consideration\n"
        if isinstance(options, list):
            for i, opt in enumerate(options, 1):
                md += f"{i}. {opt}\n"
        else:
            md += str(options)
        md += "\n"

    if first_step:
        md += f"### Suggested First Step\n{first_step}\n\n"

    if further:
        md += "### Further Investigations if Needed\n"
        for f in further:
            md += f"- {f}\n"
        md += "\n"

    if advisory:
        md += f"### Clinical Note\n*{advisory}*\n\n"

    md += "---\n*The treating clinician retains full authority over all management decisions.*"
    return md


# ── Stage functions ───────────────────────────────────────────
def stage1_assess(symptoms_text, duration, age_group, sex):
    """Stage 1: symptoms → follow-up questions (primary) + tentative differential (secondary)."""
    if not symptoms_text.strip():
        return (
            "*Please enter at least one symptom.*",
            "", "", "",
            gr.update(interactive=False),
            gr.update(interactive=False),
        )
    symptoms = [s.strip().lower() for s in symptoms_text.split(",") if s.strip()]
    prompt = build_prompt(symptoms, int(duration), age_group, sex, "initial_with_followup")
    try:
        raw, elapsed = run_llama(prompt)
        data = parse_json(raw)
        return (
            fmt_followup_questions(data),
            fmt_tentative_differential(data, elapsed),
            fmt_redflags(data),
            fmt_rationale(data),
            gr.update(interactive=True),   # enable stage 2
            gr.update(interactive=False),  # keep stage 3 locked
        )
    except Exception as e:
        return (
            f"**Error:** {e}",
            "", "", "",
            gr.update(interactive=False),
            gr.update(interactive=False),
        )


def stage2_recommend(symptoms_text, duration, age_group, sex, followup_answers):
    """Stage 2: follow-up answers → recommended tests (primary) + working differential (secondary)."""
    if not followup_answers.strip():
        return (
            "*Please enter your answers to the follow-up questions from Step 1.*",
            "", "",
            gr.update(interactive=False),
        )
    symptoms = [s.strip().lower() for s in symptoms_text.split(",") if s.strip()]
    prompt = build_prompt(
        symptoms, int(duration), age_group, sex,
        "test_recommendation", extra=followup_answers,
    )
    try:
        raw, elapsed = run_llama(prompt)
        data = parse_json(raw)
        return (
            fmt_recommended_tests(data, elapsed),
            fmt_working_differential(data),
            fmt_rationale(data),
            gr.update(interactive=True),  # enable stage 3
        )
    except Exception as e:
        return (
            f"**Error:** {e}",
            "", "",
            gr.update(interactive=False),
        )


def stage3_advise(symptoms_text, duration, age_group, sex, test_results):
    """Stage 3: investigation results → clinical advisory (doctor makes the decision)."""
    if not test_results.strip():
        return "*Please enter the investigation results from Step 2 before proceeding.*", ""
    symptoms = [s.strip().lower() for s in symptoms_text.split(",") if s.strip()]
    prompt = build_prompt(
        symptoms, int(duration), age_group, sex,
        "advisory_conclusion", extra=test_results,
    )
    try:
        raw, elapsed = run_llama(prompt)
        data = parse_json(raw)
        return fmt_advisory(data, elapsed), fmt_rationale(data)
    except Exception as e:
        return f"**Error:** {e}", ""


# ── Build UI ──────────────────────────────────────────────────
def build_ui():
    # Gradio 6 moved `css` and `theme` from the Blocks constructor to launch();
    # passing them here is ignored, which silently drops the styling.
    with gr.Blocks(title="Aletheia — Clinical Decision Support") as demo:

        gr.HTML("""
        <div class="aletheia-header">
            <h1>⚕ Aletheia Diagnostic AI</h1>
            <p>Offline-first clinical decision support · Soroti University, Uganda ·
               Arapai Technologies International Limited</p>
            <span class="offline-badge">🔒 Fully Offline — No Internet Required</span>
        </div>
        <div class="disclaimer">
            <strong>⚠ Clinical Disclaimer:</strong> Aletheia is a research prototype and decision
            support tool. It does not replace clinical judgement. All outputs must be reviewed by a
            qualified healthcare professional. Not a licensed medical device.
        </div>
        """)

        # ── Shared patient inputs ─────────────────────────────
        gr.HTML('<span class="step-badge">PATIENT PRESENTATION</span>')
        with gr.Row():
            with gr.Column(scale=2):
                symptoms_input = gr.Textbox(
                    label="Symptoms",
                    placeholder="fever, headache, neck stiffness, vomiting",
                    info="Enter symptoms separated by commas",
                    lines=3,
                )
            with gr.Column(scale=1):
                duration_input = gr.Slider(
                    label="Duration (days)", minimum=0, maximum=365, value=2, step=1
                )
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
        gr.HTML('<hr><span class="step-badge">STEP 1 — Assess Presentation &amp; Generate Follow-up Questions</span>')
        step1_btn = gr.Button("▶  Run Step 1: Assess Symptoms", variant="primary", size="lg")

        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("#### Follow-up Questions *(answer all before Step 2)*")
                stage1_followup = gr.Markdown("*Enter symptoms above and click Run Step 1.*")
            with gr.Column(scale=1):
                gr.Markdown("#### Tentative Differential *(context only — not yet actionable)*")
                stage1_diff = gr.Markdown("")

        with gr.Row():
            with gr.Column(scale=1):
                stage1_rf  = gr.Markdown(label="⚠️ Red Flags")
            with gr.Column(scale=1):
                stage1_rat = gr.Markdown(label="📋 Clinical Rationale")

        # ── STEP 2 ────────────────────────────────────────────
        gr.HTML('<hr><span class="step-badge">STEP 2 — Answer Follow-up Questions → Investigation Recommendations</span>')
        gr.Markdown(
            "*Answer every follow-up question from Step 1 below, then click Run Step 2. "
            "Step 2 is locked until Step 1 has completed successfully.*"
        )
        followup_answers = gr.Textbox(
            label="Answers to Follow-up Questions",
            placeholder=(
                "e.g. Kernig sign positive, no rash, vaccinated against meningitis, "
                "last travel 2 weeks ago, no TB contacts..."
            ),
            lines=4,
            info="Answer all follow-up questions from Step 1 before clicking Run Step 2",
        )
        step2_btn = gr.Button(
            "▶  Run Step 2: Get Investigation Recommendations",
            variant="primary",
            interactive=False,
        )

        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("#### Recommended Investigations *(perform these before Step 3)*")
                stage2_tests = gr.Markdown("*Complete Step 1 first.*")
            with gr.Column(scale=1):
                gr.Markdown("#### Working Differential *(context for test selection — not a confirmed diagnosis)*")
                stage2_working_diff = gr.Markdown("")

        stage2_rat = gr.Markdown(label="📋 Rationale for Investigation Selection")

        # Human-action separator — the system does not perform this step
        gr.HTML("""
        <div class="action-box">
            <strong>🔬 CLINICIAN ACTION REQUIRED:</strong> Perform the investigations listed above.
            The system does not simulate or perform tests. When real results are available,
            enter them in Step 3.
        </div>
        """)

        # ── STEP 3 ────────────────────────────────────────────
        gr.HTML('<hr><span class="step-badge">STEP 3 — Enter Investigation Results → Clinical Advisory</span>')
        gr.Markdown(
            "*Enter the actual results of the investigations from Step 2. "
            "Aletheia will provide a clinical advisory to support your management decision. "
            "Step 3 is locked until Step 2 has completed successfully.*"
        )
        test_results_input = gr.Textbox(
            label="Investigation Results",
            placeholder=(
                "e.g. CSF: cloudy, WBC 2000 cells/µL (90% neutrophils), protein elevated, "
                "glucose low. Malaria RDT: negative. Blood culture: pending..."
            ),
            lines=5,
            info="Enter actual results of all investigations performed in Step 2",
        )
        step3_btn = gr.Button(
            "▶  Run Step 3: Get Clinical Advisory",
            variant="primary",
            interactive=False,
        )

        with gr.Row():
            with gr.Column(scale=2):
                stage3_advisory = gr.Markdown("*Complete Steps 1 and 2 first.*")
            with gr.Column(scale=1):
                stage3_rat = gr.Markdown(label="📋 Final Rationale")

        # ── Example cases ─────────────────────────────────────
        gr.HTML('<hr>')
        gr.Markdown("### Example Cases — Click to load, then run Step 1")
        gr.Examples(
            examples=[
                ["fever, headache, neck stiffness, vomiting",               2,  "adult",   "unknown"],
                ["altered consciousness, seizures, fever, pallor",           2,  "child",   "female"],
                ["cough, weight loss, night sweats, haemoptysis",           30,  "adult",   "male"],
                ["seizures, severe headache, high blood pressure, oedema",   1,  "adult",   "female"],
                ["heavy bleeding after delivery, pallor, tachycardia",       0,  "adult",   "female"],
                ["chest pain, sweating, left arm pain",                      1,  "elderly", "male"],
                ["severe wasting, oedema, anorexia",                        90,  "child",   "unknown"],
                ["bite wound, local swelling, ptosis",                       0,  "adult",   "male"],
            ],
            inputs=[symptoms_input, duration_input, age_input, sex_input],
            label="Click any case to load it",
        )

        gr.HTML("""
        <hr style="margin-top:24px; border-color:#dee2e6;">
        <div style="text-align:center; color:#6c757d; font-size:0.82rem; padding:12px;">
            <strong>Aletheia</strong> · Soroti University, Uganda · ADTC 2026 ·
            <a href="https://github.com/JosephWalusimbi-eng/Aletheia" target="_blank">GitHub</a>
        </div>
        """)

        # ── Wire buttons — enforce stage ordering ─────────────
        # Step 1 success → enables step 2, resets step 3 to locked
        step1_btn.click(
            fn=stage1_assess,
            inputs=[symptoms_input, duration_input, age_input, sex_input],
            outputs=[stage1_followup, stage1_diff, stage1_rf, stage1_rat,
                     step2_btn, step3_btn],
            show_progress="full",
        )

        # Step 2 success → enables step 3
        step2_btn.click(
            fn=stage2_recommend,
            inputs=[symptoms_input, duration_input, age_input, sex_input, followup_answers],
            outputs=[stage2_tests, stage2_working_diff, stage2_rat, step3_btn],
            show_progress="full",
        )

        # Step 3 → clinical advisory
        step3_btn.click(
            fn=stage3_advise,
            inputs=[symptoms_input, duration_input, age_input, sex_input, test_results_input],
            outputs=[stage3_advisory, stage3_rat],
            show_progress="full",
        )

    return demo


if __name__ == "__main__":
    print("\nAletheia — Starting web interface...")
    print("Open your browser at: http://localhost:7860\n")
    demo = build_ui()
    demo.queue(default_concurrency_limit=1)
    demo.launch(
        css=CSS,
        theme=gr.themes.Soft(primary_hue="cyan", secondary_hue="slate"),
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        # the launcher opens the browser itself; avoid a duplicate tab
        inbrowser=not os.environ.get("ALETHEIA_NO_BROWSER"),
        show_error=True,
        max_threads=1,
    )
