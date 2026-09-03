#!/usr/bin/env python3
"""
run.py
======
Aletheia — Single-Stage Inference CLI
Runs one stage of the clinical pipeline from the command line.

Usage:
    # Stage 1 — initial assessment + follow-up questions (default)
    python3 run.py --symptoms "fever, headache, neck stiffness" --duration 2

    # Stage 2 — investigation recommendations (requires --extra with follow-up answers)
    python3 run.py --symptoms "fever, headache, neck stiffness" --duration 2 \
        --stage test_recommendation \
        --extra "Kernig positive, no rash, vaccinated, no TB contact"

    # Stage 3 — clinical advisory (requires --extra with investigation results)
    python3 run.py --symptoms "fever, headache, neck stiffness" --duration 2 \
        --stage advisory_conclusion \
        --extra "CSF cloudy, WBC 2000, protein high, glucose low, Malaria RDT negative"
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inference.aletheia import diagnose
from inference.safety import HazardRefusal, screen
from inference import recall

STAGES = [
    "initial_with_followup",
    "test_recommendation",
    "advisory_conclusion",
]

STAGE_REQUIRES_EXTRA = {
    "test_recommendation":  "follow-up answers (--extra)",
    "advisory_conclusion":  "investigation results (--extra)",
}


def _maybe_save(args, result) -> None:
    """Store this stage under its case key when --save was given.

    Nothing is written without the flag. A recalled result is already in the
    store, and a stage that produced nothing parsable is not worth keeping.
    """
    if not args.save or result.get("recalled"):
        return

    response = result.get("response") or {}
    if not response or list(response) == ["raw_response"]:
        print("Not saved: the stage returned no parsable output.", file=sys.stderr)
        return

    # The schema records no identity, so the free-text arguments are the only
    # route one could take into the store.
    warning = recall.identifier_warning(args.symptoms or "", args.extra or "")
    if warning:
        print(f"Not saved: {warning}", file=sys.stderr)
        return

    try:
        case = recall.save(
            result["symptoms"], args.duration, args.age, args.sex,
            args.stage, response, args.extra,
        )
    except Exception as exc:
        print(f"Not saved: {exc}", file=sys.stderr)
        return
    print(f"Saved to the case store as {case.key}.")


def _print_result(args, result) -> None:
    """Render one stage's result, and store it when --save was given."""
    print(f"\n[{result['elapsed_seconds']:.1f}s]")

    if args.json:
        print(json.dumps(result, indent=2))
        return

    response = result.get("response", {})
    raw = result.get("raw", "")

    # Stage 1 output
    fup = response.get("follow_up_questions", [])
    if fup:
        print("\nFOLLOW-UP QUESTIONS:")
        for i, q in enumerate(fup, 1):
            print(f"  {i}. {q}")

    diffs = (response.get("tentative_differentials") or
             response.get("ranked_differentials") or [])
    if diffs:
        print("\nTENTATIVE DIFFERENTIAL (context only — not yet actionable):")
        for i, d in enumerate(diffs, 1):
            prob = d.get("probability", 0)
            sev  = d.get("severity", "")
            print(f"  {i}. {d.get('condition',''):<38} {prob*100:.0f}%  [{sev}]")

    # Stage 2 output
    tests = response.get("recommended_tests", [])
    if tests:
        print("\nRECOMMENDED INVESTIGATIONS (perform these before Stage 3):")
        for i, t in enumerate(tests, 1):
            print(f"  {i}. {t}")

    working = response.get("working_differential", [])
    if working:
        print("\nWORKING DIFFERENTIAL (context for test selection):")
        for i, d in enumerate(working, 1):
            prob = d.get("probability", 0)
            print(f"  {i}. {d.get('condition',''):<38} {prob*100:.0f}%")

    # Stage 3 output
    diagnosis = (response.get("likely_diagnosis") or
                 response.get("final_diagnosis") or "")
    if diagnosis:
        confidence = response.get("diagnostic_confidence", "")
        conf_str = f" (confidence: {confidence})" if confidence else ""
        print(f"\nADVISORY — LIKELY DIAGNOSIS: {diagnosis}{conf_str}")
        print("(Decision authority: treating clinician)")

    options = (response.get("management_options") or
               response.get("management") or [])
    if options:
        print("\nMANAGEMENT OPTIONS FOR CLINICIAN'S CONSIDERATION:")
        if isinstance(options, list):
            for i, m in enumerate(options, 1):
                print(f"  {i}. {m}")
        else:
            print(f"  {options}")

    first_step = response.get("recommended_first_step", "")
    if first_step:
        print(f"\nSUGGESTED FIRST STEP: {first_step}")

    advisory = response.get("clinical_advisory_note", "")
    if advisory:
        print(f"\nCLINICAL NOTE: {advisory}")

    # Shared fields
    red_flags = response.get("red_flags", [])
    if red_flags:
        print("\n⚠  RED FLAGS:")
        for rf in red_flags:
            print(f"  ▸ {rf}")

    rationale = (response.get("clinical_rationale") or
                 response.get("rationale_for_tests") or
                 response.get("reasoning") or "")
    if rationale:
        print(f"\nRATIONALE:\n  {rationale}")

    if not any([fup, diffs, tests, working, diagnosis, options, red_flags, rationale]):
        print("\nMODEL RESPONSE:")
        print(raw[:2000])

    print()

    _maybe_save(args, result)


def main():
    parser = argparse.ArgumentParser(
        description="Aletheia — Single-Stage Clinical Decision Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Pipeline stages:
  initial_with_followup   Stage 1: tentative differential + follow-up questions (default)
  test_recommendation     Stage 2: priority investigations after follow-up answers
  advisory_conclusion     Stage 3: management advisory after investigation results

The --extra flag carries the context each stage needs:
  Stage 2: provide the clinician's answers to the Stage 1 follow-up questions
  Stage 3: provide the actual investigation results from Stage 2
        """,
    )
    parser.add_argument(
        "--symptoms", "-s",
        help="Comma-separated list of symptoms",
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=1,
        help="Duration of symptoms in days (default: 1)",
    )
    parser.add_argument(
        "--age",
        default="adult",
        choices=["neonate", "infant", "child", "adolescent", "adult", "elderly"],
        help="Patient age group (default: adult)",
    )
    parser.add_argument(
        "--sex",
        default="unknown",
        choices=["male", "female", "unknown"],
        help="Patient sex (default: unknown)",
    )
    parser.add_argument(
        "--stage",
        default="initial_with_followup",
        choices=STAGES,
        help="Pipeline stage to run (default: initial_with_followup)",
    )
    parser.add_argument(
        "--extra",
        default="",
        help=(
            "Context required for stages 2 and 3. "
            "For test_recommendation: follow-up answers. "
            "For advisory_conclusion: investigation results."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON response",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Inference timeout in seconds (default: 600)",
    )

    # Saved cases. Recall is opt-in here, unlike the interactive interfaces:
    # a scripted run — a benchmark above all — must measure the model, and a
    # store that silently answered for it would report throughput that no
    # inference produced.
    parser.add_argument(
        "--recall",
        action="store_true",
        help="Answer from a saved case when one matches, instead of running the model",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save this stage's result to the case store when it completes",
    )
    parser.add_argument(
        "--list-cases",
        action="store_true",
        help="List saved cases and exit",
    )
    parser.add_argument(
        "--forget",
        metavar="KEY",
        help="Delete one saved case by key and exit",
    )

    args = parser.parse_args()

    if args.list_cases:
        info = recall.stats()
        print(f"\n{info['count']} saved case(s) — {info['edited']} clinician-edited, "
              f"{info['stale']} stale")
        print(f"Store: {info['path']}\n")
        for case in recall.all_cases():
            mark = "edited " if case.edited else "as-is  "
            flag = "  (stale)" if case.is_stale() else ""
            print(f"  {case.key}  {case.saved_on}  {mark}  {case.stage}{flag}")
            print(f"      {', '.join(case.inputs.get('symptoms', []))} · "
                  f"{case.inputs.get('duration_band','?')} days · "
                  f"{case.inputs.get('age_group','?')} · {case.inputs.get('sex','?')}")
        return

    if args.forget:
        print("Deleted." if recall.delete(args.forget) else "No case with that key.")
        return

    if not args.symptoms:
        print("Error: --symptoms is required.", file=sys.stderr)
        sys.exit(1)

    symptoms = [s.strip().lower() for s in args.symptoms.split(",") if s.strip()]
    if not symptoms:
        print("Error: No symptoms provided.", file=sys.stderr)
        sys.exit(1)

    if args.stage in STAGE_REQUIRES_EXTRA and not args.extra.strip():
        required = STAGE_REQUIRES_EXTRA[args.stage]
        print(
            f"Error: Stage '{args.stage}' requires {required}.\n"
            f"Use --extra to provide it.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"\nAletheia Diagnostic AI")
    print(f"{'─'*40}")
    print(f"Symptoms : {', '.join(symptoms)}")
    print(f"Duration : {args.duration} day(s)")
    print(f"Patient  : {args.age}, {args.sex}")
    print(f"Stage    : {args.stage}")
    if args.extra:
        print(f"Extra    : {args.extra[:80]}{'...' if len(args.extra) > 80 else ''}")
    print(f"{'─'*40}")

    # Saved cases, when asked for. The screen runs first, so a hazardous request
    # is refused on a matched case exactly as it is on a cold run — the store is
    # not a way around the guardrail.
    recalled = None
    if args.recall:
        refusal = screen(args.symptoms, args.extra)
        if refusal is not None:
            print(f"\nREFUSED IN CODE - {refusal.label}", file=sys.stderr)
            print(f"  {refusal.message}", file=sys.stderr)
            print(f"  {refusal.guidance}", file=sys.stderr)
            sys.exit(2)
        try:
            recalled = recall.lookup(symptoms, args.duration, args.age,
                                     args.sex, args.stage, args.extra)
        except Exception:
            recalled = None       # a broken store falls through to the model

    if recalled is not None:
        print(f"\n{recalled.provenance()}")
        result = {
            "response": recalled.data,
            "raw": "",
            "elapsed_seconds": 0.0,
            "symptoms": symptoms,
            "duration_days": args.duration,
            "reasoning_type": args.stage,
            "recalled": recalled.to_dict(),
        }
        _print_result(args, result)
        return

    print("Running inference...", flush=True)

    try:
        result = diagnose(
            symptoms=symptoms,
            duration_days=args.duration,
            age_group=args.age,
            sex=args.sex,
            reasoning_type=args.stage,
            extra=args.extra,
            timeout=args.timeout,
        )
    except HazardRefusal as exc:
        # Refused in code before the model ran. Exit 2, so a script can tell a
        # refusal apart from a crash.
        r = exc.refusal
        print(f"\nREFUSED IN CODE - {r.label}", file=sys.stderr)
        print(f"  {r.message}", file=sys.stderr)
        print(f"  {r.guidance}", file=sys.stderr)
        sys.exit(2)
    except FileNotFoundError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nInference failed: {e}", file=sys.stderr)
        sys.exit(1)

    _print_result(args, result)


if __name__ == "__main__":
    main()
