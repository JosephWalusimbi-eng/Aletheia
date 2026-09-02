# Verification task: does Aletheia actually implement the specified clinical flow?

## Your job

Do NOT assume the code is correct because it runs without errors or
because variable/function names sound right. Read the actual logic
in `aletheia/server.py`, `cli.py`, and `inference/aletheia.py`, trace what
each step really sends to the model and really does with the
response, and compare that against the exact specification below.
Report mismatches honestly, including partial or "close enough"
mismatches — do not round up a near-match to a full match.

## The specification (the system MUST do exactly this)

1. **Input** — A patient or doctor enters symptoms (free text or
   structured fields).
2. **Processing** — The system processes those symptoms.
3. **Follow-up questions** — The system asks follow-up questions.
   These questions exist specifically to help CONFIRM or narrow
   down clinical possibilities — they are not generic chit-chat
   and not yet a diagnosis.
4. **Test recommendations** — After the follow-up questions are
   answered, the system's next output must be RECOMMENDED TESTS
   for the doctor to go perform. At this stage it should NOT yet
   present a confirmed diagnosis or final differential as the
   headline output — the headline output of this stage is "go run
   these tests," even if a working/tentative differential is shown
   alongside it.
5. **Human action (outside the system)** — The doctor actually
   performs the recommended tests. The system does not simulate
   or perform this step itself.
6. **Test results re-entered** — The doctor enters the real test
   results back into the system.
7. **Final output** — The system uses the test results to support
   the doctor in deciding on medication or further action. The
   final decision authority must clearly rest with the doctor —
   the system should be framed as advisory/supportive at this
   stage, not as issuing an autonomous final verdict the doctor
   has no role in.

## Specific checks to run, one at a time

For EACH of the following, check the actual code (not just
docstrings/comments) and report PASS / PARTIAL / FAIL with the
exact file and line number as evidence:

**Check 1 — Step ordering**
Does the code enforce this exact order: symptoms → follow-up
questions → test recommendations → test results → final
medication/action guidance? Or does it skip a step, reorder steps,
or merge two steps into one network/model call that the user can't
actually distinguish?

**Check 2 — Step 3 vs Step 4 distinction**
This is the one most likely to be implemented wrong. After the
follow-up questions are answered, does the very next model output
to the user genuinely foreground TEST RECOMMENDATIONS as the
primary output? Or does it actually present a refined
DIFFERENTIAL DIAGNOSIS as the primary output, with tests only as
a secondary list? Quote the actual prompt sent to the model at
this stage and the actual key(s) read from the JSON response to
settle this — do not guess from variable names alone.

**Check 3 — Final-step framing**
At the final step (after test results are entered), does the
system's output and any surrounding UI text/copy clearly frame the
doctor as making the actual medication/action decision? Or does
the system's output read as a final, closed diagnosis/treatment
plan presented as fact, with no language indicating the doctor
retains decision authority? Quote the actual text shown to the
user at this step.

**Check 4 — Consistency between the web UI and cli.py**
Do BOTH interfaces implement the same 4-stage flow identically, or
has one of them drifted from the other (e.g. one has 3 stages, the
other has 4; one labels stage 2 differently than the other)? List
every difference found between the two implementations of this
flow, however small.

**Check 5 — What happens if a user skips a stage**
If a user tries to jump straight from symptoms entry to entering
"test results" without ever going through the follow-up or test
recommendation stages, what actually happens? Does the system
prevent this, silently allow it with broken/missing context, or
crash? This matters because the spec describes a REQUIRED sequence,
not an optional one.

## Required output format

For each of the 5 checks above, give:
- **Verdict:** PASS / PARTIAL / FAIL
- **Evidence:** exact file, function/line, and (where relevant) the
  literal prompt string or JSON key being used
- **If PARTIAL or FAIL:** a one-sentence description of exactly what
  the code does instead of what the spec asks for

End with a single summary table of all 5 checks and an overall
verdict: does the implemented system match the specified flow, or
not. If it does not fully match, state plainly which check(s) are
the actual blocker, ranked by how serious the mismatch is for
clinical safety/usefulness (e.g. Check 3's framing issue is more
serious than a minor wording inconsistency in Check 4).

Do not fix anything yet. This is a verification task only — report
findings first, wait for instructions before changing any code.
