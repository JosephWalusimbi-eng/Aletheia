# Aletheia - Offline Clinical Decision Support AI

Aletheia is an offline-first clinical decision support system designed for district hospitals and health centres in sub-Saharan Africa. It runs entirely on-device using a quantized language model via [llama.cpp](https://github.com/ggerganov/llama.cpp) - no internet connection is required at any point.

**Aletheia does not diagnose. It supports the clinician's reasoning through a structured three-stage pipeline.**

---

## What it does

Aletheia guides a clinician through a structured reasoning process for a patient presentation. The process has three system stages and one human stage:

```
[Clinician] Enter symptoms
      ↓
[Stage 1]  Generate follow-up questions  ←─── Aletheia
      ↓
[Clinician] Answer follow-up questions
      ↓
[Stage 2]  Recommend investigations      ←─── Aletheia
      ↓
[Clinician] Perform the investigations (outside the system)
      ↓
[Clinician] Enter investigation results
      ↓
[Stage 3]  Clinical advisory             ←─── Aletheia
      ↓
[Clinician] Make the management decision
```

### Stage 1: Follow-up Questions
After symptoms are entered, Aletheia produces:
- **Follow-up questions** (primary output) - targeted questions to narrow the differential
- Tentative differential (secondary, context only - not yet actionable)
- Red flags requiring immediate escalation

### Stage 2: Investigation Recommendations
After the clinician answers the follow-up questions, Aletheia produces:
- **Recommended investigations** (primary output) - specific tests in priority order
- Working differential (secondary, context explaining why these tests were chosen)

The system does not simulate or perform tests. The clinician performs them in the real world.

### Stage 3: Clinical Advisory
After the clinician enters the actual investigation results, Aletheia produces:
- **Clinical advisory** - likely diagnosis, management options, suggested first step
- All output is framed as advisory. The treating clinician makes every final management decision.

---

## Interfaces

### Launcher (`start_aletheia.sh`)
Starts the web UI and opens it in the default browser, so a clinician never has to
use a terminal:

```bash
bash start_aletheia.sh
```

It finds the virtual environment, checks that the model file is present, waits for
the server to come up, and opens the page. If Aletheia is already running it
just reopens the tab. To add it to the desktop applications menu:

```bash
bash start_aletheia.sh --install-shortcut
```

### Web UI (`aletheia/server.py`)
A self-contained web interface with enforced stage ordering:
- The Stage 2 button is disabled until Stage 1 completes successfully
- The Stage 3 button is disabled until Stage 2 completes successfully
- Each stage's primary output is prominently displayed
- **The answer streams as it is generated.** A stage takes 40 to 60 seconds; the
  text appears token by token in a live panel, with elapsed seconds and a running
  rate, so a slow local model never looks like a hung one. When the stage ends the
  live panel is replaced by the parsed panels, and the status line shows
  llama.cpp's own measured figure — e.g. `Completed in 47.2s, 122 tokens, 5.67 tok/s`.
- **A runtime rail in the header** shows what is actually loaded on this machine:
  the GGUF filename, its size on disk, the thread count, CPU only. "Fully offline"
  stops being a claim and becomes something the reader can check. If the model file
  or the llama.cpp binary is missing, it says so there rather than after a minute
  of waiting.
- **Refusals are shown as answers, not errors** — see [Safety](#safety-refused-in-code).

It is served by Python's standard library over a small JSON API, and the page carries
its own CSS and JavaScript. There is no web framework and no external asset, so it
loads instantly and works with no internet connection.

```bash
python3 aletheia/server.py
# Opens at http://localhost:7860
```

The server binds `127.0.0.1`, so the console is reachable from this laptop only.
Patient presentations are typed into it, so it is not published to the ward network
unless you deliberately ask for that:

```bash
ALETHEIA_HOST=0.0.0.0 python3 aletheia/server.py   # reachable from the whole LAN
ALETHEIA_PORT=8080     python3 aletheia/server.py   # different port
```

Routes: `GET /api/status` (runtime facts), `POST /api/stage/stream`
(server-sent events: `refused` | `token` | `result` | `error`),
`POST /api/stage` (the original blocking JSON call, kept for scripts), and
`POST /api/recall/lookup` | `/save` | `/delete` for saved cases.

### Interactive Terminal (`cli.py`)
A rich terminal interface that walks through all three stages sequentially:
- Follow-up answers are required before Stage 2 runs
- Investigation results are required before Stage 3 runs (case is paused if not provided)

```bash
python3 cli.py
```

### Single-Stage CLI (`run.py`)
For scripting or testing a single pipeline stage from the command line.

```bash
# Stage 1 — initial assessment + follow-up questions (default)
python3 run.py --symptoms "fever, headache, neck stiffness" --duration 2

# Stage 2 — investigation recommendations (requires --extra with follow-up answers)
python3 run.py --symptoms "fever, headache, neck stiffness" --duration 2 \
    --stage test_recommendation \
    --extra "Kernig sign positive, no rash, vaccinated, no TB contacts"

# Stage 3 — clinical advisory (requires --extra with investigation results)
python3 run.py --symptoms "fever, headache, neck stiffness" --duration 2 \
    --stage advisory_conclusion \
    --extra "CSF cloudy, WBC 2000 cells/µL 90% neutrophils, protein high, glucose low, malaria RDT negative"

# Output raw JSON
python3 run.py --symptoms "fever, headache" --duration 3 --json

# Saved cases: answer from the store when one matches, and keep this result
python3 run.py --symptoms "fever, headache" --duration 3 --recall --save
python3 run.py --list-cases
python3 run.py --forget <key>
```

Recall is opt-in here and nowhere else. A scripted run — a benchmark above all —
must measure the model, and a store that quietly answered for it would report
throughput that no inference produced.

---

## Saved cases

A stage costs 40-60 s on the target laptop, and the same presentation walks in
more than once. So a finished stage can be kept, and a later stage with the same
inputs can be answered from the record instead of from llama.cpp.

At the end of a run you are offered three things, with no default: **save**,
**edit then save**, or **exit without saving**. The middle one carries the
clinical value — what is stored after an edit is a record a clinician read,
corrected and signed off, and it is marked as such when it comes back.

A match is computed over the normalised symptom set, the duration band, the age
group, the sex, the stage, and that stage's own input. Four rules hold:

- A recalled result says so, with its date and whether it was edited. It is
  never dressed up as a fresh answer.
- The model is always one click or keystroke away, whatever the store returned.
- The safety screen runs **before** recall, so a paediatric dosing question is
  refused on a matched case exactly as on a cold run.
- Cases age. Past a configurable threshold they are shown with their age, so
  you can judge whether year-old reasoning still applies.

A saved case describes a presentation, not a person: Aletheia has no field in
which a patient identity could be recorded — symptoms, a duration, an age *band*
and sex — so the store has nothing to disclose even if the laptop is lost. The
free-text boxes are the one channel left, so the save step warns when the text
looks like it names someone.

The store is one JSON file beside the model weights (override with
`ALETHEIA_CASE_STORE`), never synced and never transmitted. Delete it and
Aletheia runs exactly as before.

```bash
python3 -m inference.recall     # self-checks for the store and the case key
```

---

## Safety: refused in code

Aletheia is advisory. It helps a clinician decide; it does not prescribe. That
boundary is enforced in `inference/safety.py`, on the text the clinician typed,
**before any prompt is built and before llama.cpp is launched** — not by asking the
model to hold an instruction. A 3B model asked for a neonatal gentamicin dose will
usually answer, and a wrong number there is the most dangerous output this system
can produce.

Five classes are refused:

| Class | Refused |
|---|---|
| `paediatric_dose` | paediatric or weight-based dose calculations |
| `controlled_substance` | doses for opioids, sedatives, anaesthetic agents |
| `drug_dose` | drug doses generally |
| `prescription` | "prescribe X", "which antibiotic should I give" |
| `lethal_dose` | lethal, fatal or harmful-dose questions |

A refusal is an outcome, not a crash: the web UI renders it in place of the output
with the class name and what to do instead, the terminal CLI prints it as its own
panel, and `run.py` exits **2** (distinct from 1 for a real failure).

Every class needs two keys to fire — a request marker *and* a hazard marker — so
ordinary clinical history passes straight through. `gave 500 mg ceftriaxone at 0600,
creatinine now 180` is a legitimate Stage 3 input and is not refused; `what dose of
ceftriaxone should I give` is. The class list is a clinical-policy decision, kept
deliberately short. After editing it, run the self-checks, which assert both that
hazards are caught and that ordinary presentations are not:

```bash
python3 -m inference.safety
```

---

## Setup

### Requirements
- Python 3.11 (minimum; the ADTC profiler requires ≥ 3.11, Python 3.12 untested)
- [llama.cpp](https://github.com/ggerganov/llama.cpp) built locally (`llama-cli` binary)
- A GGUF model file (e.g. `aletheia_q4km.gguf`)
- `rich` (terminal UI, optional) - `pip install rich`

The web UI needs no third-party package: it runs on Python's standard library.

### Configuration
Create `inference/config.json`:

```json
{
    "llama_cli": "/path/to/llama.cpp/build/bin/llama-cli",
    "model_path": "/path/to/model/aletheia_q4km.gguf",
    "context_size": 1024,
    "threads": 4,
    "max_tokens": 512,
    "temperature": 0.1
}
```

### Tuning inference speed

`benchmark/optimize.sh` measures generation throughput across thread counts and
writes the fastest into `config.json`:

```bash
bash benchmark/optimize.sh              # measure and apply
bash benchmark/optimize.sh --dry-run    # measure only
```

This is worth running once per machine. llama.cpp does dense matrix work that does
not benefit from hyperthreading, so using every logical core is usually slower than
using only the physical ones. On the development laptop (4 cores, 8 threads) the
measured difference was 7.10 tokens per second at 4 threads against 4.14 at 8, which
cut a full pipeline stage from 79 seconds to 46.

If `config.json` is absent, the system falls back to:
- `llama_cli`: `~/llama.cpp/build/bin/llama-cli`
- `model_path`: `model/aletheia_q4km.gguf` (relative to project root)

---

## Project structure

```
aletheia/
├── aletheia/
│   ├── server.py           Web UI server (standard library, streaming, 127.0.0.1)
│   └── ui/index.html       Web UI page (self-contained CSS and JavaScript)
├── inference/
│   ├── aletheia.py         Core inference wrapper, prompt builder, token streaming
│   ├── safety.py           Hazard classes refused in code, before the model runs
│   └── config.json         Runtime configuration (create this)
├── cli.py                  Interactive terminal interface
├── run.py                  Single-stage command-line tool
└── model/                  GGUF model file (downloaded, gitignored)
```

---

## Clinical context

Aletheia is designed for resource-limited settings where:
- Internet connectivity is unreliable or unavailable
- GPU hardware is not available (runs on CPU only)
- Clinicians may be working alone without specialist support
- Presentations are weighted toward conditions prevalent in East and Central Africa

The model is prompted to consider availability of investigations at district hospital level and to prioritise conditions relevant to the local epidemiology.

---

## Disclaimer

Aletheia is a research prototype developed at Soroti University, Uganda, in collaboration with Arapai Technologies International Limited. It is presented at ADTC 2026.

**Aletheia is not a licensed medical device.** It does not replace clinical judgement. Every output - including the final Stage 3 advisory - must be evaluated and acted upon by a qualified healthcare professional. The treating clinician retains full authority over all patient management decisions.
