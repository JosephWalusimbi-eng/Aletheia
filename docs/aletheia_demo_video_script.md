# Aletheia — ADTC 2026 Demo Video Script
**Target length: 2:30–2:45**

---

## ⚠️ CRITICAL: This demo now has THREE inference waits, not one

Your real system is a 3-step flow (symptoms → follow-up → test
results), and each step takes ~25-35 real seconds to generate.
That's 75-105 seconds of raw waiting inside a video with a
~165 second total budget. You MUST compress every single wait,
not just one, or the video will run 4-5 minutes and lose judges.

**Rule for every wait in Scenes 4, 5, and 6 below:** speed up
4-6x with a small on-screen label like "4x speed — model
reasoning" so it reads as intentional pacing, not hidden lag.
Do this consistently at every step so the technique feels like
a deliberate editing choice, not a cover-up at one spot only.

If, after a first full-length rough cut, you're running long even
with all three waits compressed, the safest cut is to **trim Scene
6 (test results → final conclusion) down to its result only** —
skip narrating the input, just show "test results entered" as a
quick on-screen text card, then cut straight to the confirmed
diagnosis. Steps 1 and 2 (initial differential + follow-up
refinement) are the more distinctive, judge-impressing part of the
flow and should stay intact even if Scene 6 gets trimmed.

---

## Pre-recording checklist (do this BEFORE you hit record)

- [ ] VM/laptop fully booted, no other apps running (avoid lag/notifications on screen)
- [ ] Close all unrelated browser tabs and desktop icons
- [ ] Gradio app (`app.py`) NOT yet started — you'll start it on camera
- [ ] Have `cli.py` or `run.py` ready in a terminal, NOT yet run
- [ ] Wi-Fi currently ON (you'll disconnect it on camera as proof)
- [ ] Pick ONE test case in advance and know it cold — recommend:
      **"fever, headache, neck stiffness, vomiting" (bacterial meningitis)**
      — it's your most clinically dramatic, highest-stakes example
- [ ] Pre-decide your Step 2 follow-up answers (e.g. "Kernig's sign
      positive, photophobia present, no recent travel") — DO NOT
      improvise these live, write them down so you can type fast
- [ ] Pre-decide your Step 3 test results (e.g. "CSF cloudy, WBC
      elevated, glucose low, protein high") — same rule, write first
- [ ] Run through the ENTIRE 3-step flow once, off-camera, before
      recording — confirm all three steps return clean, expected
      output with YOUR chosen answers. Do not discover a bad/garbled
      output for the first time while recording.
- [ ] Decide: screen recording software (OBS, or built-in) set to 1080p min
- [ ] Test your mic levels with a 5-second clip before the real take

---

## SCENE 1 — Cold open / hook (0:00–0:15)

**Visual:** Face cam or voiceover over a simple title card: "Aletheia"

**Script:**
> "In rural Uganda, one doctor serves twenty-five thousand patients.
> There's no internet at most clinics. No cloud. No backup.
> This is Aletheia — an offline AI that helps clinicians reach a
> diagnosis, with nothing but the laptop in front of them."

**Note:** Keep this tight. 15 seconds, no more. Judges watch dozens of these.

---

## SCENE 2 — Prove it's offline (0:15–0:35)

**Visual:** Show your desktop/taskbar. Click Wi-Fi icon. Visibly disconnect.

**Script (while disconnecting):**
> "First — let's remove any doubt. I'm disconnecting from the
> internet right now, on camera. No Wi-Fi. No cloud connection.
> Everything you're about to see runs entirely on this machine —
> an Intel i5, 8 gigabytes of RAM. The kind of laptop you'd
> actually find in a district hospital."

**Visual cue:** Make sure the "no internet" / disconnected icon is
clearly visible in the OS taskbar for at least 2-3 seconds — don't
rush past it, this is your single most important proof shot.

---

## SCENE 3 — Launch the system (0:35–0:55)

**Visual:** Open terminal, `cd ~/Aletheia`, run:
```bash
source venv/bin/activate
python3 app.py
```
Browser opens to `localhost:7860`

**Script:**
> "I'm launching Aletheia now — this is a Gradio interface running
> locally on this machine. Notice the URL: localhost. Not a website.
> Nothing leaving this laptop."

**Note:** If `app.py` has any startup lag, you can speed this segment
up 2x in editing — startup time isn't part of your performance claim,
only inference time is, so no honesty issue compressing this part.

---

## SCENE 4 — Step 1: Enter symptoms, get initial differential (0:55–1:20)

**Visual:** Type the symptoms into the web UI input field

**Script:**
> "Let's walk through a real case, the way a clinician actually would.
> A patient presents with fever, headache, neck stiffness, and
> vomiting — for two days. I enter that, and ask Aletheia for an
> initial differential diagnosis."

**Visual:** Click submit. Output appears (sped up per Scene 5 method
below — apply this same compress-and-acknowledge technique to EVERY
wait in this video, not just once).

**On result appearing, briefly highlight:**
> "Bacterial meningitis, ranked highest — alongside viral meningitis
> and cerebral malaria as close differentials. But Aletheia doesn't
> stop there."

---

## SCENE 5 — Step 2: Follow-up questions → refined differential (1:20–1:50)

**Visual:** Scroll to the follow-up questions Aletheia generated.
Read 1-2 of them on screen. Type believable clinical answers into
the follow-up input box (decide these in advance — e.g. "Kernig's
sign positive, photophobia present, no recent travel").

**Script:**
> "This is the part that makes Aletheia feel like a real clinical
> partner, not a lookup table. It asks targeted follow-up questions
> — here, about neck rigidity testing and photophobia — to narrow
> things down. I'll answer as the examining clinician would."

**Visual:** Submit answers. Wait (compressed, same technique).
Refined differential + recommended investigations appear.

**Script:**
> "And the differential sharpens. Bacterial meningitis is now the
> clear leading diagnosis, and Aletheia recommends the specific
> investigations to confirm it — lumbar puncture, blood cultures,
> CSF analysis."

---

## SCENE 6 — Step 3 → 4: Enter test results, get final conclusion (1:50–2:20)

**Visual:** Type plausible test results into the input field (decide
in advance — e.g. "CSF cloudy, WBC elevated, glucose low, protein
high — consistent with bacterial infection")

**Script:**
> "Now the doctor has results back from the lab. I'll enter those
> findings — and this is the step that closes the loop. Aletheia
> doesn't just diagnose; it takes real test results and gives a
> final, confirmed conclusion."

**Visual:** Submit. Wait (compressed). Final output appears showing
confirmed diagnosis + recommended management/next steps.

**Script:**
> "Confirmed bacterial meningitis, with recommended next steps for
> treatment. The doctor makes the final call on medication — that's
> their job, not the model's — but Aletheia has walked the entire
> clinical reasoning path alongside them: symptoms, questions,
> tests, confirmation."

---

## SCENE 7 — The numbers (2:20–2:40)

**Visual:** Cut to a simple on-screen graphic/overlay (or just speak
over the same UI) showing:
- 1.80 GB model size
- 3.22 GB peak RAM (of 8 GB ceiling)
- 50 clinical conditions covered
- Top-1: 80% / Top-3: 100% accuracy (your own held-out eval)

**Script:**
> "The full model is under two gigabytes. It peaks at just over
> three gigabytes of RAM — well inside the eight-gigabyte target.
> It covers fifty conditions weighted for disease patterns across
> East Africa, and in our own evaluation, the correct diagnosis
> appeared in the top three suggestions one hundred percent of
> the time. All of it — symptoms to confirmed diagnosis — without
> a single connection to the internet."

---

## SCENE 8 — Close (2:40–2:55)

**Visual:** Return to face cam, or a closing title card with project
name + team/university

**Script:**
> "Aletheia won't replace a doctor. But for the clinician who's
> alone, overwhelmed, and offline — it's a partner that walks the
> full path with them: symptoms, questions, tests, confirmation.
> Thank you."

**On-screen text (final card, hold for 3-4 seconds):**
> Aletheia — Offline-First Clinical Decision Support
> [Your university / team name]
> ADTC 2026

---

## Post-recording checklist

- [ ] Watch the full video once before uploading — check audio sync
- [ ] Confirm the Wi-Fi disconnect moment is clearly visible, not rushed
- [ ] Confirm total runtime is 2:30–2:45, trim if over 3:00
- [ ] Export at 1080p minimum
- [ ] Upload, set thumbnail (you already have one ready)
- [ ] Double check video title/description matches your Devpost
      project name exactly: "Aletheia: An Offline-First Clinical
      Decision Support System for Differential Diagnosis in
      Low-Resource Healthcare Settings"

---

## Optional: if you have extra time/energy

A 10-15 second B-roll style addition showing the CLI version
(`python3 cli.py`) running the same case in parallel/split-screen
can be a nice technical credibility touch for judges who want to see
"under the hood" — but only add this if it doesn't push you past 3:00.
It is NOT required; the web UI demo alone fully satisfies the brief.
