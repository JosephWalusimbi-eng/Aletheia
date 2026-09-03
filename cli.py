#!/usr/bin/env python3
"""
cli.py
======
Aletheia — Interactive Terminal Clinical Decision Support
Three-stage clinical pipeline:
  Stage 1: Enter symptoms → Follow-up Questions (primary) + Tentative Differential
  Stage 2: Answer follow-up questions → Recommended Investigations (primary output)
  Stage 3: Enter investigation results → Clinical Advisory (doctor retains decision authority)

Stages are sequential and enforced:
  - Stage 2 requires follow-up answers (re-prompted if empty)
  - Stage 3 requires actual investigation results (ends case if not provided)
"""

import sys
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from inference.aletheia import build_prompt, run_inference
from inference.safety import HazardRefusal, screen

console = Console() if HAS_RICH else None

SEVERITY_COLOUR = {
    "Critical": "bold red",
    "High":     "bold orange1",
    "Moderate": "bold yellow",
    "Low":      "bold green",
}

HEADER = """
╔══════════════════════════════════════════════════════════════╗
║   ALETHEIA Diagnostic AI                                     ║
║   Offline Clinical Decision Support · Soroti University, UG  ║
║   Running entirely offline — no internet required            ║
╚══════════════════════════════════════════════════════════════╝
"""

# ── Helpers ───────────────────────────────────────────────────
def cprint(text, style=""):
    if HAS_RICH:
        console.print(text, style=style)
    else:
        print(re.sub(r'\[.*?\]', '', text))

def get_input(prompt_text, default=""):
    if HAS_RICH:
        return Prompt.ask(f"[bold cyan]{prompt_text}[/bold cyan]", default=default).strip()
    val = input(f"{prompt_text}: ").strip()
    return val if val else default

def confirm(prompt_text):
    if HAS_RICH:
        return Confirm.ask(f"[bold yellow]{prompt_text}[/bold yellow]")
    return input(f"{prompt_text} (y/n): ").lower().startswith("y")

def rule(title=""):
    if HAS_RICH:
        console.rule(f"[bold cyan]{title}[/bold cyan]" if title else "")
    else:
        print(f"\n{'─'*55} {title}")

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

# ── Display functions ─────────────────────────────────────────
def display_followup_questions(data: dict) -> list:
    """Primary output of Stage 1 — questions to narrow the differential."""
    fup = (data.get("follow_up_questions") or
           data.get("follow_up") or
           data.get("questions") or [])
    rule("STAGE 1 — FOLLOW-UP QUESTIONS")
    if fup:
        cprint("[bold yellow]Answer all of these before proceeding to Stage 2:[/bold yellow]"
               if HAS_RICH else "Answer all of these before proceeding to Stage 2:")
        for i, q in enumerate(fup, 1):
            cprint(f"  [yellow]{i}. {q}[/yellow]" if HAS_RICH else f"  {i}. {q}")
    else:
        cprint("[dim]No follow-up questions generated.[/dim]"
               if HAS_RICH else "No follow-up questions generated.")
    return fup


def display_tentative_differential(data: dict, elapsed: float):
    """Secondary output of Stage 1 — shown as context only, not actionable."""
    diffs = (data.get("tentative_differentials") or
             data.get("ranked_differentials") or
             data.get("differentials") or
             data.get("differential_diagnosis") or [])
    cprint(f"\n[dim]Tentative differential — context only, not yet actionable [{elapsed}s]:[/dim]"
           if HAS_RICH else f"\nTentative differential — context only [{elapsed}s]:")
    if diffs and HAS_RICH:
        table = Table(box=box.SIMPLE, border_style="dim",
                      show_header=True, header_style="dim")
        table.add_column("Condition", style="dim white")
        table.add_column("Probability", justify="right", style="dim")
        table.add_column("Severity", style="dim")
        for d in diffs:
            prob = d.get("probability", 0)
            sev  = d.get("severity", "")
            table.add_row(d.get("condition", ""), f"{prob*100:.0f}%", sev)
        console.print(table)
    elif diffs:
        for d in diffs:
            prob = d.get("probability", 0)
            print(f"  {d.get('condition',''):<40} {prob*100:.0f}%  [{d.get('severity','')}]")
    else:
        cprint("[dim]No tentative differential returned.[/dim]"
               if HAS_RICH else "No tentative differential returned.")


def display_redflags(data: dict):
    rf = data.get("red_flags") or []
    if rf:
        cprint("\n[bold red]!! RED FLAGS -- requiring immediate attention:[/bold red]"
               if HAS_RICH else "\n!! RED FLAGS -- requiring immediate attention:")
        for f in rf:
            cprint(f"  [red]> {f}[/red]" if HAS_RICH else f"  > {f}")


def display_rationale(data: dict):
    r = (data.get("clinical_rationale") or
         data.get("rationale_for_tests") or
         data.get("reasoning") or "")
    if r:
        if HAS_RICH:
            console.print(Panel(r, title="[bold]Clinical Rationale[/bold]",
                               border_style="dim", padding=(0, 2)))
        else:
            print(f"\nCLINICAL RATIONALE:\n  {r}")


def display_recommended_tests(data: dict, elapsed: float):
    """Primary output of Stage 2 — the investigations the clinician must perform."""
    tests = (data.get("recommended_tests") or
             data.get("priority_tests") or
             data.get("investigations") or [])
    rule("STAGE 2 — RECOMMENDED INVESTIGATIONS")
    cprint(f"[dim]{elapsed}s[/dim]")
    if tests:
        cprint("\n[bold]Perform these investigations before entering results in Stage 3:[/bold]"
               if HAS_RICH else "\nPerform these investigations before entering results in Stage 3:")
        for i, t in enumerate(tests, 1):
            cprint(f"  [bold cyan]{i}.[/bold cyan] {t}" if HAS_RICH else f"  {i}. {t}")
    else:
        cprint("[yellow]No test recommendations generated — check model output.[/yellow]"
               if HAS_RICH else "No test recommendations generated.")
    return tests


def display_working_differential(data: dict):
    """Secondary output of Stage 2 — context explaining why these tests were chosen."""
    diffs = (data.get("working_differential") or
             data.get("tentative_differentials") or
             data.get("ranked_differentials") or
             data.get("differentials") or [])
    if diffs:
        cprint("\n[dim]Working differential (context for test selection — not a confirmed diagnosis):[/dim]"
               if HAS_RICH else "\nWorking differential (context — not a confirmed diagnosis):")
        for i, d in enumerate(diffs, 1):
            prob = d.get("probability", 0)
            cprint(f"  [dim]{i}. {d.get('condition','')} ({prob*100:.0f}%)[/dim]"
                   if HAS_RICH else f"  {i}. {d.get('condition','')} ({prob*100:.0f}%)")


def display_advisory(data: dict, elapsed: float):
    """Output of Stage 3 — advisory only, clinician makes all final decisions."""
    rule("STAGE 3 — CLINICAL ADVISORY")
    cprint(f"[dim]{elapsed}s[/dim]")

    if HAS_RICH:
        console.print(Panel(
            "[bold yellow]ADVISORY ONLY[/bold yellow]\n"
            "This output is decision support. The treating clinician makes "
            "all final patient management decisions.",
            border_style="yellow", padding=(0, 2),
        ))
    else:
        print("\n⚠  ADVISORY ONLY — The treating clinician makes all final management decisions.\n")

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

    if diagnosis:
        conf_str = f" (confidence: {confidence})" if confidence else ""
        if HAS_RICH:
            console.print(Panel(
                f"[bold]{diagnosis}[/bold]{conf_str}",
                title="[bold]Likely Diagnosis[/bold]",
                border_style="cyan",
            ))
        else:
            print(f"\nLIKELY DIAGNOSIS: {diagnosis}{conf_str}")

    if options:
        cprint("\n[bold]Management Options for Clinician's Consideration:[/bold]"
               if HAS_RICH else "\nMANAGEMENT OPTIONS FOR CLINICIAN'S CONSIDERATION:")
        if isinstance(options, list):
            for i, m in enumerate(options, 1):
                cprint(f"  {i}. {m}")
        else:
            cprint(f"  {options}")

    if first_step:
        cprint(f"\n[bold]Suggested First Step:[/bold] {first_step}"
               if HAS_RICH else f"\nSUGGESTED FIRST STEP: {first_step}")

    if further:
        cprint("\n[dim]Further investigations if needed:[/dim]"
               if HAS_RICH else "\nFurther investigations if needed:")
        for f in further:
            cprint(f"  [dim]- {f}[/dim]" if HAS_RICH else f"  - {f}")

    if advisory:
        cprint(f"\n[italic]{advisory}[/italic]" if HAS_RICH else f"\n{advisory}")

    if not any([diagnosis, options, first_step]):
        cprint("[yellow]No structured advisory — showing raw:[/yellow]"
               if HAS_RICH else "No structured advisory — showing raw:")
        print(str(data)[:800])

    if HAS_RICH:
        console.rule(
            "[dim]The treating clinician retains full authority over all management decisions.[/dim]"
        )
    else:
        print(
            "\n─── The treating clinician retains full authority over all management decisions. ───"
        )


# ── Input collection ──────────────────────────────────────────
def collect_symptoms() -> tuple:
    rule("PATIENT PRESENTATION")
    cprint("[dim]Enter symptoms one per line. Blank line when done.[/dim]"
           if HAS_RICH else "Enter symptoms one per line. Blank line when done.")

    symptoms = []
    while True:
        sym = get_input(f"  Symptom {len(symptoms)+1}")
        if not sym:
            if len(symptoms) >= 1:
                break
            cprint("[red]Enter at least one symptom.[/red]"
                   if HAS_RICH else "Enter at least one symptom.")
        else:
            if sym.lower() in ("quit", "exit", "q"):
                return None, None, None, None
            symptoms.append(sym.lower())

    duration_str = get_input("Duration (days)", "1")
    try:
        duration = int(duration_str)
    except ValueError:
        duration = 1

    cprint("\nAge group: [1] Neonate  [2] Infant  [3] Child  [4] Adolescent  "
           "[5] Adult  [6] Elderly")
    age_map = {
        "1": "neonate", "2": "infant", "3": "child",
        "4": "adolescent", "5": "adult", "6": "elderly",
    }
    age_group = age_map.get(get_input("Select", "5"), "adult")

    sex_str = get_input("Sex (m/f/unknown)", "unknown")
    sex = ("male"    if sex_str.lower().startswith("m") else
           "female"  if sex_str.lower().startswith("f") else "unknown")

    return symptoms, duration, age_group, sex


# ── Inference wrapper ─────────────────────────────────────────
def run_stage(reasoning_type: str, symptoms, duration, age_group, sex,
              extra: str = "") -> tuple[dict, float]:
    # Refused in code, before the prompt exists. See inference/safety.py.
    refusal = screen(", ".join(symptoms), extra)
    if refusal is not None:
        raise HazardRefusal(refusal)

    prompt = build_prompt(symptoms, duration, age_group, sex, reasoning_type, extra=extra)

    cprint("\n[dim]Running inference...[/dim]" if HAS_RICH else "\nRunning inference...")
    raw, elapsed = run_inference(prompt, timeout=600)

    return parse_json(raw), elapsed


def display_refusal(stage: int, refusal) -> None:
    """A refusal is an answer, not a crash — print it as one."""
    if HAS_RICH:
        console.print(Panel(
            f"[bold]{refusal.message}[/bold]\n\n[dim]{refusal.guidance}[/dim]",
            title=f"[bold red]Stage {stage} refused in code · {refusal.label}[/bold red]",
            border_style="red", box=box.ROUNDED,
        ))
    else:
        print(f"\nSTAGE {stage} REFUSED IN CODE - {refusal.label}")
        print(f"  {refusal.message}")
        print(f"  {refusal.guidance}")


# ── Main clinical flow ────────────────────────────────────────
def run_case():
    symptoms, duration, age_group, sex = collect_symptoms()
    if symptoms is None:
        return False

    # ── STAGE 1: Symptoms → follow-up questions ───────────────
    cprint(
        "\n[bold cyan]═══ STAGE 1: Assess Symptoms & Generate Follow-up Questions ═══[/bold cyan]"
        if HAS_RICH else
        "\n═══ STAGE 1: Assess Symptoms & Generate Follow-up Questions ═══"
    )

    try:
        data1, elapsed1 = run_stage(
            "initial_with_followup", symptoms, duration, age_group, sex
        )
    except HazardRefusal as r:
        display_refusal(1, r.refusal)
        return True
    except Exception as e:
        cprint(f"[bold red]Stage 1 failed:[/bold red] {e}"
               if HAS_RICH else f"Stage 1 failed: {e}")
        return True

    fup = display_followup_questions(data1)
    display_tentative_differential(data1, elapsed1)
    display_redflags(data1)
    display_rationale(data1)

    # ── STAGE 2: Follow-up answers → investigation recommendations
    cprint(
        "\n[bold cyan]═══ STAGE 2: Answer Follow-up Questions → Investigation Recommendations ═══[/bold cyan]"
        if HAS_RICH else
        "\n═══ STAGE 2: Answer Follow-up Questions → Investigation Recommendations ═══"
    )
    cprint(
        "[dim]Enter your answers to the follow-up questions above.[/dim]"
        if HAS_RICH else
        "Enter your answers to the follow-up questions above."
    )

    followup_answers = get_input("Your answers")

    if not followup_answers:
        cprint(
            "\n[yellow]Follow-up answers are required to generate investigation recommendations.\n"
            "Enter 'none' if no additional information is available.[/yellow]"
            if HAS_RICH else
            "\nFollow-up answers are required. Enter 'none' if no additional information is available."
        )
        followup_answers = get_input("Your answers (or 'none')")

    if not followup_answers:
        followup_answers = "No additional clinical history available."
        cprint(
            "[dim]Proceeding with no additional history — "
            "recommendations based on initial presentation only.[/dim]"
            if HAS_RICH else
            "Proceeding with no additional history — recommendations based on initial presentation only."
        )

    try:
        data2, elapsed2 = run_stage(
            "test_recommendation", symptoms, duration, age_group, sex,
            extra=followup_answers,
        )
    except HazardRefusal as r:
        display_refusal(2, r.refusal)
        return True
    except Exception as e:
        cprint(f"[bold red]Stage 2 failed:[/bold red] {e}"
               if HAS_RICH else f"Stage 2 failed: {e}")
        return True

    display_recommended_tests(data2, elapsed2)
    display_working_differential(data2)
    display_rationale(data2)

    # Human-action gate — system does not perform or simulate this step
    if HAS_RICH:
        console.print(Panel(
            "[bold]CLINICIAN ACTION REQUIRED:[/bold] Perform the investigations listed above.\n"
            "The system does not simulate or perform tests.\n"
            "Return here and enter the actual results when they are available.",
            border_style="cyan", padding=(0, 2),
        ))
    else:
        print(
            "\n─── CLINICIAN ACTION REQUIRED ─────────────────────────────────────────────\n"
            "    Perform the investigations listed above.\n"
            "    The system does not simulate or perform tests.\n"
            "    Enter actual results when ready.\n"
            "────────────────────────────────────────────────────────────────────────────"
        )

    # ── STAGE 3: Investigation results → clinical advisory ────
    cprint(
        "\n[bold cyan]═══ STAGE 3: Enter Investigation Results → Clinical Advisory ═══[/bold cyan]"
        if HAS_RICH else
        "\n═══ STAGE 3: Enter Investigation Results → Clinical Advisory ═══"
    )
    cprint(
        "[dim]Enter the actual results of the investigations from Stage 2.[/dim]"
        if HAS_RICH else
        "Enter the actual results of the investigations from Stage 2."
    )

    test_results = get_input("Investigation results")

    if not test_results:
        cprint(
            "\n[bold yellow]Investigation results are required before the clinical advisory "
            "can be generated.[/bold yellow]\n"
            "[dim]Perform the recommended investigations first, then re-run this case.[/dim]"
            if HAS_RICH else
            "\nInvestigation results are required — perform the recommended tests first."
        )
        return True

    try:
        data3, elapsed3 = run_stage(
            "advisory_conclusion", symptoms, duration, age_group, sex,
            extra=test_results,
        )
    except HazardRefusal as r:
        display_refusal(3, r.refusal)
        return True
    except Exception as e:
        cprint(f"[bold red]Stage 3 failed:[/bold red] {e}"
               if HAS_RICH else f"Stage 3 failed: {e}")
        return True

    display_advisory(data3, elapsed3)
    display_rationale(data3)
    return True


# ── Entry point ───────────────────────────────────────────────
def main():
    if HAS_RICH:
        console.print(Panel(
            "[bold cyan]ALETHEIA[/bold cyan] [white]Diagnostic AI[/white]\n"
            "[dim]Three-Stage Clinical Decision Support · Soroti University, Uganda[/dim]\n"
            "[dim]Running entirely offline — no internet required[/dim]",
            border_style="cyan", padding=(1, 4),
        ))
    else:
        print(HEADER)

    cprint(
        "[dim]Type 'quit' or 'exit' at any symptom prompt to stop.[/dim]\n"
        if HAS_RICH else "Type 'quit' or 'exit' to stop.\n"
    )
    cprint(
        "[bold yellow]DISCLAIMER:[/bold yellow] Aletheia is a decision support tool. "
        "It does not replace clinical judgement. The treating clinician makes all final decisions.\n"
        if HAS_RICH else
        "DISCLAIMER: Aletheia does not replace clinical judgement. "
        "The treating clinician makes all final decisions.\n"
    )

    session = 0
    while True:
        session += 1
        cprint(f"\n[bold cyan]─── Case {session} ───[/bold cyan]"
               if HAS_RICH else f"\n─── Case {session} ───")
        try:
            cont = run_case()
            if not cont:
                break
        except (KeyboardInterrupt, EOFError):
            break

        try:
            if not confirm("\nAssess another patient?"):
                break
        except (KeyboardInterrupt, EOFError):
            break

    cprint("\n[bold]Session ended. Goodbye.[/bold]"
           if HAS_RICH else "\nSession ended. Goodbye.")


if __name__ == "__main__":
    main()
