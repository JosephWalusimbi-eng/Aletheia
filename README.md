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
- A live elapsed-second counter runs while the model is working

It is served by Python's standard library over a small JSON API, and the page carries
its own CSS and JavaScript. There is no web framework and no external asset, so it
loads instantly and works with no internet connection.

```bash
python3 aletheia/server.py
# Opens at http://localhost:7860
```

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
│   ├── server.py           Web UI server (standard library, three-stage flow)
│   └── ui/index.html       Web UI page (self-contained CSS and JavaScript)
├── inference/
│   ├── aletheia.py         Core inference wrapper and prompt builder
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
