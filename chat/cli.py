#!/usr/bin/env python3
"""
cli.py
======
Aletheia — Interactive Terminal Clinical Decision Support
Multi-step clinical reasoning flow:

  Step 1: Enter symptoms → Initial Differential Diagnosis
  Step 2: Answer follow-up questions → Refined Differential + Investigations
  Step 3: Enter test results → Final Diagnosis + Management

Usage:
    source venv/bin/activate
    python3 chat/cli.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich import box
    from rich.rule import Rule
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from inference.aletheia import diagnose, build_prompt, load_config
import subprocess, time, re

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
        # strip rich markup for plain output
        plain = re.sub(r'\[.*?\]', '', text)
        print(plain)

def get_input(prompt_text, default=""):
    if HAS_RICH:
        return Prompt.ask(f"[bold cyan]{prompt_text}[/bold cyan]",
                         default=default).strip()
    else:
        val = input(f"{prompt_text}: ").strip()
        return val if val else default

def confirm(prompt_text):
    if HAS_RICH:
        return Confirm.ask(f"[bold yellow]{prompt_text}[/bold yellow]")
    else:
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
def display_differentials(data: dict, elapsed: float, step: str = ""):
    diffs = (data.get("ranked_differentials") or
             data.get("differentials") or
             data.get("differential_diagnosis") or [])

    rule(f"STEP {step} — DIFFERENTIAL DIAGNOSIS" if step else "DIFFERENTIAL DIAGNOSIS")
    cprint(f"[dim]Response time: {elapsed}s[/dim]")

    if diffs and HAS_RICH:
        table = Table(box=box.ROUNDED, border_style="cyan",
                      show_header=True, header_style="bold cyan")
        table.add_column("Rank", style="dim", width=5)
        table.add_column("Condition", style="bold white")
        table.add_column("Probability", justify="right")
        table.add_column("Severity")
        for i, d in enumerate(diffs, 1):
            prob = d.get("probability", 0)
            sev  = d.get("severity", "")
            col  = SEVERITY_COLOUR.get(sev, "white")
            bar  = "█" * int(prob * 20)
            from rich.text import Text
            table.add_row(str(i), d.get("condition",""),
                         f"{prob*100:.0f}%  {bar}", Text(sev, style=col))
        console.print(table)
    elif diffs:
        for i, d in enumerate(diffs, 1):
            prob = d.get("probability", 0)
            sev  = d.get("severity", "")
            print(f"  {i}. {d.get('condition',''):<38} {prob*100:.0f}%  [{sev}]")
    else:
        cprint("[yellow]No structured differential output — showing raw:[/yellow]")
        print(str(data)[:800])

def display_redflags(data: dict):
    rf = data.get("red_flags") or []
    if rf:
        cprint("\n[bold red]⚠  RED FLAGS:[/bold red]" if HAS_RICH else "\n⚠  RED FLAGS:")
        for f in rf:
            cprint(f"  [red]▸ {f}[/red]" if HAS_RICH else f"  ▸ {f}")

def display_rationale(data: dict):
    r = (data.get("clinical_rationale") or
         data.get("reasoning") or
         data.get("rationale") or "")
    if r:
        if HAS_RICH:
            console.print(Panel(r, title="[bold]Clinical Rationale[/bold]",
                               border_style="dim", padding=(0, 2)))
        else:
            print(f"\nCLINICAL RATIONALE:\n  {r}")

def display_tests(data: dict):
    tests = (data.get("priority_tests") or
             data.get("recommended_tests") or
             data.get("additional_tests") or
             data.get("priority_investigations") or
             data.get("investigations") or [])
    if tests:
        cprint("\n[bold]PRIORITY INVESTIGATIONS:[/bold]" if HAS_RICH
               else "\nPRIORITY INVESTIGATIONS:")
        for i, t in enumerate(tests, 1):
            cprint(f"  {i}. {t}")

def display_followup(data: dict) -> list:
    fup = (data.get("follow_up_questions") or
           data.get("follow_up") or
           data.get("questions") or [])
    if fup:
        cprint("\n[bold yellow]FOLLOW-UP QUESTIONS:[/bold yellow]" if HAS_RICH
               else "\nFOLLOW-UP QUESTIONS:")
        for i, q in enumerate(fup, 1):
            cprint(f"  [yellow]{i}. {q}[/yellow]" if HAS_RICH else f"  {i}. {q}")
    return fup

def display_conclusion(data: dict, elapsed: float):
    rule("FINAL DIAGNOSIS & MANAGEMENT")
    cprint(f"[dim]Response time: {elapsed}s[/dim]")

    diagnosis = data.get("final_diagnosis") or data.get("diagnosis") or ""
    management = data.get("management") or data.get("treatment") or data.get("immediate_management") or []

    if diagnosis:
        if HAS_RICH:
            console.print(Panel(f"[bold green]{diagnosis}[/bold green]",
                               title="[bold]Final Diagnosis[/bold]",
                               border_style="green"))
        else:
            print(f"\nFINAL DIAGNOSIS: {diagnosis}")

    if management:
        cprint("\n[bold]IMMEDIATE MANAGEMENT:[/bold]" if HAS_RICH
               else "\nIMMEDIATE MANAGEMENT:")
        if isinstance(management, list):
            for i, m in enumerate(management, 1):
                cprint(f"  {i}. {m}")
        else:
            cprint(f"  {management}")

    if not diagnosis and not management:
        cprint("[yellow]No structured conclusion — showing raw:[/yellow]")
        print(str(data)[:800])

# ── Input collection ──────────────────────────────────────────
def collect_symptoms() -> tuple:
    rule("PATIENT PRESENTATION")
    cprint("[dim]Enter symptoms one per line. Press Enter twice when done.[/dim]"
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
    age_map = {"1":"neonate","2":"infant","3":"child",
               "4":"adolescent","5":"adult","6":"elderly"}
    age_group = age_map.get(get_input("Select", "5"), "adult")

    sex_str = get_input("Sex (m/f/unknown)", "unknown")
    sex = ("male" if sex_str.lower().startswith("m") else
           "female" if sex_str.lower().startswith("f") else "unknown")

    return symptoms, duration, age_group, sex

# ── Run inference wrapper ─────────────────────────────────────
def run_step(prompt_type: str, symptoms, duration, age_group, sex,
             extra: str = "") -> tuple[dict, float]:
    """Run one inference step and return (parsed_data, elapsed)."""
    import subprocess, time

    cfg = load_config()
    llama_bin = cfg["llama_cli"]
    model_path = cfg["model_path"]

    if prompt_type == "initial":
        prompt = build_prompt(symptoms, duration, age_group, sex, "initial_differential")
    elif prompt_type == "followup":
        prompt = build_prompt(symptoms, duration, age_group, sex, "follow_up_questions")
    elif prompt_type == "refine":
        prompt = (
            "### System:\nYou are Aletheia, an offline-first clinical decision support AI. "
            "Always respond in structured JSON format.\n\n"
            "### Instruction:\nRefine the differential diagnosis and recommend priority "
            "investigations based on additional clinical history.\n\n"
            "### Input:\n" +
            json.dumps({"symptoms": symptoms, "duration_days": duration,
                       "patient_age_group": age_group, "sex": sex,
                       "additional_history": extra}) +
            "\n\n### Response:\n"
        )
    elif prompt_type == "conclude":
        prompt = (
            "### System:\nYou are Aletheia, an offline-first clinical decision support AI. "
            "Always respond in structured JSON format.\n\n"
            "### Instruction:\nGiven investigation results, provide a final diagnosis "
            "and immediate management plan.\n\n"
            "### Input:\n" +
            json.dumps({"symptoms": symptoms, "duration_days": duration,
                       "patient_age_group": age_group, "sex": sex,
                       "investigation_results": extra}) +
            "\n\n### Response:\n"
        )
    else:
        prompt = build_prompt(symptoms, duration, age_group, sex, prompt_type)

    cmd = [llama_bin, "-m", model_path,
           "-p", prompt,
           "-n", str(cfg.get("max_tokens", 512)),
           "-c", str(cfg.get("context_size", 1024)),
           "-t", str(cfg.get("threads", 4)),
           "--temp", str(cfg.get("temperature", 0.1)),
           "--no-display-prompt", "-ngl", "0", "--log-disable"]

    cprint("\n[dim]Running inference...[/dim]" if HAS_RICH else "\nRunning inference...")
    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    elapsed = round(time.time() - t0, 1)

    if result.returncode != 0:
        raise RuntimeError(f"llama-cli failed:\n{result.stderr[-200:]}")

    return parse_json(result.stdout.strip()), elapsed

# ── Main clinical flow ────────────────────────────────────────
def run_case():
    # Collect patient info
    symptoms, duration, age_group, sex = collect_symptoms()
    if symptoms is None:
        return False  # user quit

    # ── STEP 1: Initial differential ─────────────────────────
    cprint("\n[bold cyan]═══ STEP 1: Initial Differential Diagnosis ═══[/bold cyan]"
           if HAS_RICH else "\n═══ STEP 1: Initial Differential Diagnosis ═══")

    try:
        data1, elapsed1 = run_step("initial", symptoms, duration, age_group, sex)
        display_differentials(data1, elapsed1, "1")
        display_redflags(data1)
        display_rationale(data1)
        fup = display_followup(data1)
    except Exception as e:
        cprint(f"[bold red]Step 1 failed:[/bold red] {e}" if HAS_RICH
               else f"Step 1 failed: {e}")
        return True

    # ── STEP 2: Follow-up and refinement ─────────────────────
    cprint("\n[bold cyan]═══ STEP 2: Refine Differential ═══[/bold cyan]"
           if HAS_RICH else "\n═══ STEP 2: Refine Differential ═══")

    if fup:
        cprint("\n[dim]Answer the follow-up questions above (or press Enter to skip):[/dim]"
               if HAS_RICH else "\nAnswer follow-up questions (or press Enter to skip):")
    else:
        cprint("\n[dim]Enter any additional clinical history:[/dim]"
               if HAS_RICH else "\nEnter any additional clinical history:")

    followup_answers = get_input("Your answers")

    if followup_answers:
        try:
            data2, elapsed2 = run_step("refine", symptoms, duration, age_group, sex,
                                       extra=followup_answers)
            display_differentials(data2, elapsed2, "2")
            display_tests(data2)
            display_rationale(data2)
        except Exception as e:
            cprint(f"[bold red]Step 2 failed:[/bold red] {e}" if HAS_RICH
                   else f"Step 2 failed: {e}")
    else:
        cprint("[dim]Step 2 skipped.[/dim]" if HAS_RICH else "Step 2 skipped.")
        display_tests(data1)

    # ── STEP 3: Investigation results → Final conclusion ──────
    cprint("\n[bold cyan]═══ STEP 3: Final Conclusion ═══[/bold cyan]"
           if HAS_RICH else "\n═══ STEP 3: Final Conclusion ═══")
    cprint("[dim]Enter investigation results (or press Enter to skip):[/dim]"
           if HAS_RICH else "Enter investigation results (or press Enter to skip):")

    test_results = get_input("Investigation results")

    if test_results:
        try:
            data3, elapsed3 = run_step("conclude", symptoms, duration, age_group, sex,
                                       extra=test_results)
            display_conclusion(data3, elapsed3)
            display_rationale(data3)
        except Exception as e:
            cprint(f"[bold red]Step 3 failed:[/bold red] {e}" if HAS_RICH
                   else f"Step 3 failed: {e}")
    else:
        cprint("[dim]Step 3 skipped.[/dim]" if HAS_RICH else "Step 3 skipped.")

    return True

# ── Entry point ───────────────────────────────────────────────
def main():
    if HAS_RICH:
        console.print(Panel(
            "[bold cyan]ALETHEIA[/bold cyan] [white]Diagnostic AI[/white]\n"
            "[dim]Multi-Step Clinical Decision Support · Soroti University, Uganda[/dim]\n"
            "[dim]Running entirely offline — no internet required[/dim]",
            border_style="cyan", padding=(1, 4),
        ))
    else:
        print(HEADER)

    cprint("[dim]Type 'quit' or 'exit' at any symptom prompt to stop.[/dim]\n"
           if HAS_RICH else "Type 'quit' or 'exit' to stop.\n")
    cprint("[bold yellow]⚠  DISCLAIMER:[/bold yellow] Aletheia is a decision support tool. "
           "It does not replace clinical judgement.\n"
           if HAS_RICH else
           "⚠  DISCLAIMER: Aletheia does not replace clinical judgement.\n")

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

    cprint("\n[bold]Session ended. Goodbye.[/bold]" if HAS_RICH
           else "\nSession ended. Goodbye.")

if __name__ == "__main__":
    main()
