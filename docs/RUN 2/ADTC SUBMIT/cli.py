"""
cli.py
======
Aletheia — Interactive Terminal Clinical Decision Support Chatbot
Designed for clinical officers at district hospitals in sub-Saharan Africa.
Runs entirely offline. No internet required.
"""

import sys
import json
import os
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.prompt import Prompt, Confirm
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from inference.aletheia import diagnose

console = Console() if HAS_RICH else None

# ── Colours ───────────────────────────────────────────────────
SEVERITY_COLOUR = {
    "Critical": "bold red",
    "High":     "bold orange1",
    "Moderate": "bold yellow",
    "Low":      "bold green",
}

# ── Header ────────────────────────────────────────────────────
HEADER = """
╔══════════════════════════════════════════════════════════════╗
║   █████╗ ██╗     ███████╗████████╗██╗  ██╗███████╗██╗ █████╗║
║  ██╔══██╗██║     ██╔════╝╚══██╔══╝██║  ██║██╔════╝██║██╔══██╗
║  ███████║██║     █████╗     ██║   ███████║█████╗  ██║███████║
║  ██╔══██║██║     ██╔══╝     ██║   ██╔══██║██╔══╝  ██║██╔══██║
║  ██║  ██║███████╗███████╗   ██║   ██║  ██║███████╗██║██║  ██║
║  ╚═╝  ╚═╝╚══════╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝╚═╝  ╚═╝
╠══════════════════════════════════════════════════════════════╣
║  Offline Clinical Decision Support │ Soroti University, UG  ║
║  Running offline — no internet required                      ║
╚══════════════════════════════════════════════════════════════╝
"""

# ── Helpers ───────────────────────────────────────────────────
def print_header():
    if HAS_RICH:
        console.print(Panel(
            "[bold cyan]ALETHEIA[/bold cyan] [white]Diagnostic AI[/white]\n"
            "[dim]Offline Clinical Decision Support · Soroti University, Uganda[/dim]\n"
            "[dim]Running entirely offline — no internet required[/dim]",
            border_style="cyan",
            padding=(1, 4),
        ))
    else:
        print(HEADER)

def cprint(text, style=""):
    if HAS_RICH:
        console.print(text, style=style)
    else:
        print(text)

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

# ── Input collection ──────────────────────────────────────────
def collect_symptoms() -> tuple[list[str], int, str, str]:
    cprint("\n[bold]PATIENT PRESENTATION[/bold]" if HAS_RICH else "\nPATIENT PRESENTATION")
    cprint("─" * 50)

    # Symptoms
    cprint("[dim]Enter symptoms one per line. Press Enter twice when done.[/dim]"
           if HAS_RICH else "Enter symptoms one per line. Blank line when done.")
    symptoms = []
    while True:
        sym = get_input(f"  Symptom {len(symptoms)+1}")
        if not sym:
            if len(symptoms) >= 1:
                break
            cprint("[red]Please enter at least one symptom.[/red]"
                   if HAS_RICH else "Please enter at least one symptom.")
        else:
            symptoms.append(sym.lower())

    # Duration
    duration_str = get_input("Duration (days)", "1")
    try:
        duration = int(duration_str)
    except ValueError:
        duration = 1

    # Age group
    cprint("\nAge group: [1] Neonate  [2] Infant  [3] Child  [4] Adolescent  "
           "[5] Adult  [6] Elderly" if HAS_RICH else
           "\nAge group: 1=Neonate 2=Infant 3=Child 4=Adolescent 5=Adult 6=Elderly")
    age_map = {
        "1": "neonate", "2": "infant", "3": "child",
        "4": "adolescent", "5": "adult", "6": "elderly",
    }
    age_choice = get_input("Select", "5")
    age_group = age_map.get(age_choice, "adult")

    # Sex
    sex_str = get_input("Sex (m/f)", "unknown")
    sex = "male" if sex_str.lower().startswith("m") else \
          "female" if sex_str.lower().startswith("f") else "unknown"

    return symptoms, duration, age_group, sex

# ── Display results ───────────────────────────────────────────
def display_results(result: dict):
    elapsed = result.get("elapsed_seconds", 0)
    response = result.get("response", {})
    raw = result.get("raw", "")

    cprint(f"\n[dim]Response time: {elapsed:.1f}s[/dim]" if HAS_RICH
           else f"\nResponse time: {elapsed:.1f}s")

    if HAS_RICH:
        console.rule("[bold cyan]ALETHEIA ASSESSMENT[/bold cyan]")
    else:
        print("\n" + "="*55)
        print("  ALETHEIA ASSESSMENT")
        print("="*55)

    # Differential diagnosis
    differentials = response.get("ranked_differentials", [])
    if differentials and HAS_RICH:
        table = Table(
            title="Ranked Differential Diagnosis",
            box=box.ROUNDED,
            border_style="cyan",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Rank", style="dim", width=5)
        table.add_column("Condition", style="bold white")
        table.add_column("Probability", justify="right")
        table.add_column("Severity")

        for i, d in enumerate(differentials, 1):
            prob = d.get("probability", 0)
            sev = d.get("severity", "")
            col = SEVERITY_COLOUR.get(sev, "white")
            bar = "█" * int(prob * 20)
            table.add_row(
                str(i),
                d.get("condition", ""),
                f"{prob*100:.0f}%  {bar}",
                Text(sev, style=col),
            )
        console.print(table)

    elif differentials:
        print("\nRANKED DIFFERENTIAL DIAGNOSIS:")
        for i, d in enumerate(differentials, 1):
            prob = d.get("probability", 0)
            sev = d.get("severity", "")
            print(f"  {i}. {d.get('condition', ''):<35} {prob*100:.0f}%  [{sev}]")

    # Tests
    tests = (response.get("priority_tests", []) +
             response.get("recommended_tests", []) +
             response.get("additional_tests", []))
    if tests:
        cprint("\n[bold]PRIORITY INVESTIGATIONS:[/bold]" if HAS_RICH
               else "\nPRIORITY INVESTIGATIONS:")
        for i, t in enumerate(tests[:6], 1):
            cprint(f"  {i}. {t}")

    # Red flags
    red_flags = response.get("red_flags", [])
    if red_flags:
        cprint("\n[bold red]⚠  RED FLAGS:[/bold red]" if HAS_RICH
               else "\n⚠  RED FLAGS:")
        for rf in red_flags:
            cprint(f"  [red]▸ {rf}[/red]" if HAS_RICH else f"  ▸ {rf}")

    # Rationale
    rationale = (response.get("clinical_rationale", "") or
                 response.get("reasoning", ""))
    if rationale:
        if HAS_RICH:
            console.print(Panel(
                rationale,
                title="[bold]Clinical Rationale[/bold]",
                border_style="dim",
                padding=(0, 2),
            ))
        else:
            print("\nCLINICAL RATIONALE:")
            print(f"  {rationale}")

    # Follow-up questions
    fup = response.get("follow_up_questions", [])
    if fup:
        cprint("\n[bold]FOLLOW-UP QUESTIONS:[/bold]" if HAS_RICH
               else "\nFOLLOW-UP QUESTIONS:")
        for i, q in enumerate(fup[:5], 1):
            cprint(f"  {i}. {q}")

    # If no structured output — show raw
    if not differentials and not tests and not rationale:
        cprint("\n[dim]Raw model output:[/dim]" if HAS_RICH else "\nModel output:")
        cprint(raw[:1500])

    if HAS_RICH:
        console.rule(style="dim")
    else:
        print("\n" + "-"*55)

# ── Reasoning type menu ───────────────────────────────────────
def choose_reasoning_type() -> str:
    options = {
        "1": ("initial_differential",  "Differential diagnosis (default)"),
        "2": ("test_recommendation",   "Investigation recommendations"),
        "3": ("severity_assessment",   "Severity & level of care"),
        "4": ("treatment_hint",        "Immediate management"),
        "5": ("follow_up_questions",   "Follow-up questions"),
        "6": ("red_flag_identification","Red flags only"),
    }
    cprint("\n[bold]CLINICAL REASONING TASK:[/bold]" if HAS_RICH
           else "\nCLINICAL REASONING TASK:")
    for key, (_, label) in options.items():
        cprint(f"  [{key}] {label}")

    choice = get_input("Select task", "1")
    rt, label = options.get(choice, options["1"])
    cprint(f"[dim]→ {label}[/dim]" if HAS_RICH else f"→ {label}")
    return rt

# ── Main loop ─────────────────────────────────────────────────
def main():
    print_header()
    cprint("[dim]Type 'quit' or 'exit' at any time to stop.[/dim]\n"
           if HAS_RICH else "Type 'quit' or 'exit' at any time to stop.\n")
    cprint("[bold yellow]⚠  CLINICAL DISCLAIMER:[/bold yellow] Aletheia is a "
           "decision support tool. It does not replace clinical judgement. "
           "The clinician remains responsible for all decisions.\n"
           if HAS_RICH else
           "⚠  CLINICAL DISCLAIMER: Aletheia is a decision support tool. "
           "It does not replace clinical judgement.\n")

    session_count = 0

    while True:
        session_count += 1
        cprint(f"\n[bold cyan]─── Case {session_count} ───[/bold cyan]"
               if HAS_RICH else f"\n─── Case {session_count} ───")

        try:
            symptoms, duration, age_group, sex = collect_symptoms()
        except (KeyboardInterrupt, EOFError):
            cprint("\n\n[bold]Session ended. Goodbye.[/bold]" if HAS_RICH
                   else "\n\nSession ended. Goodbye.")
            break

        # Check for exit
        if symptoms and symptoms[0].lower() in ("quit", "exit", "q"):
            cprint("\n[bold]Session ended. Goodbye.[/bold]" if HAS_RICH
                   else "\nSession ended. Goodbye.")
            break

        reasoning_type = choose_reasoning_type()

        cprint("\n[dim]Running inference...[/dim]" if HAS_RICH
               else "\nRunning inference...")

        try:
            result = diagnose(
                symptoms=symptoms,
                duration_days=duration,
                age_group=age_group,
                sex=sex,
                reasoning_type=reasoning_type,
                timeout=300,
            )
            display_results(result)

        except FileNotFoundError as e:
            cprint(f"\n[bold red]Error:[/bold red] {e}" if HAS_RICH
                   else f"\nError: {e}")
        except Exception as e:
            cprint(f"\n[bold red]Inference failed:[/bold red] {e}" if HAS_RICH
                   else f"\nInference failed: {e}")

        # Continue?
        try:
            if not confirm("\nAssess another patient?"):
                cprint("\n[bold]Session ended. Goodbye.[/bold]" if HAS_RICH
                       else "\nSession ended. Goodbye.")
                break
        except (KeyboardInterrupt, EOFError):
            break

if __name__ == "__main__":
    main()
