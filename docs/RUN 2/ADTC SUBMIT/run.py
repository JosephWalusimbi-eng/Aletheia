#!/usr/bin/env python3
"""
run.py
======
Aletheia — Single-Query Inference CLI
Usage:
    python3 run.py --symptoms "fever, headache, neck stiffness" --duration 2
    python3 run.py --symptoms "altered consciousness, seizures, fever" --duration 2 --age child --sex female
    python3 run.py --symptoms "severe chest pain, sweating" --duration 1 --task severity_assessment
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inference.aletheia import diagnose

TASKS = [
    "initial_differential",
    "test_recommendation",
    "severity_assessment",
    "treatment_hint",
    "follow_up_questions",
    "red_flag_identification",
]

def main():
    parser = argparse.ArgumentParser(
        description="Aletheia — Offline Clinical Decision Support AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run.py --symptoms "fever, headache, neck stiffness" --duration 2
  python3 run.py --symptoms "chest pain, sweating, arm pain" --duration 1 --task severity_assessment
  python3 run.py --symptoms "cough, weight loss, night sweats" --duration 30 --age adult --sex male

Reasoning tasks:
  initial_differential   Ranked differential diagnosis (default)
  test_recommendation    Investigation priorities
  severity_assessment    Severity and level of care
  treatment_hint         Immediate management
  follow_up_questions    Diagnostic follow-up questions
  red_flag_identification Immediate escalation triggers
        """
    )
    parser.add_argument(
        "--symptoms", "-s",
        required=True,
        help="Comma-separated list of symptoms"
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=1,
        help="Duration of symptoms in days (default: 1)"
    )
    parser.add_argument(
        "--age",
        default="adult",
        choices=["neonate","infant","child","adolescent","adult","elderly"],
        help="Patient age group (default: adult)"
    )
    parser.add_argument(
        "--sex",
        default="unknown",
        choices=["male","female","unknown"],
        help="Patient sex (default: unknown)"
    )
    parser.add_argument(
        "--task", "-t",
        default="initial_differential",
        choices=TASKS,
        help="Clinical reasoning task (default: initial_differential)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON response"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Inference timeout in seconds (default: 300)"
    )

    args = parser.parse_args()

    # Parse symptoms
    symptoms = [s.strip().lower() for s in args.symptoms.split(",") if s.strip()]

    if not symptoms:
        print("Error: No symptoms provided.", file=sys.stderr)
        sys.exit(1)

    print(f"\nAletheia Diagnostic AI", flush=True)
    print(f"{'─'*40}")
    print(f"Symptoms : {', '.join(symptoms)}")
    print(f"Duration : {args.duration} day(s)")
    print(f"Patient  : {args.age}, {args.sex}")
    print(f"Task     : {args.task}")
    print(f"{'─'*40}")
    print("Running inference...", flush=True)

    try:
        result = diagnose(
            symptoms=symptoms,
            duration_days=args.duration,
            age_group=args.age,
            sex=args.sex,
            reasoning_type=args.task,
            timeout=args.timeout,
        )
    except FileNotFoundError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nInference failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n[{result['elapsed_seconds']:.1f}s]")

    if args.json:
        print(json.dumps(result, indent=2))
        return

    # Pretty print
    response = result.get("response", {})
    raw = result.get("raw", "")

    # Differentials
    diffs = response.get("ranked_differentials", [])
    if diffs:
        print("\nRANKED DIFFERENTIAL DIAGNOSIS:")
        for i, d in enumerate(diffs, 1):
            prob = d.get("probability", 0)
            sev = d.get("severity", "")
            cond = d.get("condition", "")
            bar = "█" * int(prob * 20)
            print(f"  {i}. {cond:<38} {prob*100:.0f}%  {bar}  [{sev}]")

    # Tests
    tests = (response.get("priority_tests", []) +
             response.get("recommended_tests", []) +
             response.get("additional_tests", []))
    if tests:
        print("\nPRIORITY INVESTIGATIONS:")
        for i, t in enumerate(tests[:6], 1):
            print(f"  {i}. {t}")

    # Red flags
    red_flags = response.get("red_flags", [])
    if red_flags:
        print("\n⚠  RED FLAGS:")
        for rf in red_flags:
            print(f"  ▸ {rf}")

    # Rationale
    rationale = (response.get("clinical_rationale", "") or
                 response.get("reasoning", ""))
    if rationale:
        print(f"\nCLINICAL RATIONALE:\n  {rationale}")

    # Fallback
    if not diffs and not tests and not rationale:
        print("\nMODEL RESPONSE:")
        print(raw[:2000])

    print()

if __name__ == "__main__":
    main()
