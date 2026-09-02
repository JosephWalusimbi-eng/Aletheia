# Aletheia — Offline-First Clinical Decision Support AI

> *From the Greek ἀλήθεια — truth, disclosure. The revealing of what is hidden.*

[![ADTC 2026](https://img.shields.io/badge/ADTC%202026-Laptop%20LLM%20Track-blue)](https://adtc-2026.devpost.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](../LICENSE)
[![Model: Qwen2.5-3B](https://img.shields.io/badge/Model-Qwen2.5--3B--Instruct-orange)](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct)
[![RAM: 3.2 GB](https://img.shields.io/badge/RAM-3.2%20GB-brightgreen)](#performance-metrics)
[![Offline](https://img.shields.io/badge/Internet-Not%20Required-success)](../install.sh)

**Aletheia** is an offline-first clinical decision support system designed for
frontline healthcare workers in district hospitals and health centres across
sub-Saharan Africa. It runs entirely on a standard 8 GB laptop with no internet
connection, providing ranked differential diagnoses, investigation recommendations,
red flag identification, and clinical reasoning for 50 disease conditions
prevalent across Africa.

---

## The Problem

In Uganda, one doctor serves approximately 25,000 patients. A clinical officer
at a district hospital may see 100 patients in a single day — fewer than 5
minutes per patient — to take a history, examine, diagnose, and treat.

Existing AI diagnostic tools require cloud servers, fast internet, and expensive
hardware. None of these are reliably available at the point of care in rural
Africa. The clinicians who need AI support the most have the least access to it.

## The Solution

Aletheia runs the entire clinical reasoning pipeline **on-device**:

- ✅ **No internet required** — ever, at inference time
- ✅ **No GPU required** — runs on CPU only
- ✅ **1.80 GB model file** — fits on a USB drive
- ✅ **3,281 MB peak RAM** — 3,887 MB below the 7,168 MB ADTC ceiling
- ✅ **Web UI + CLI** — browser interface or terminal, launched from a desktop icon
- ✅ **50 clinical conditions** weighted for African disease epidemiology
- ✅ **Three enforced reasoning stages** — follow-up questions, investigations, advisory

---

## Hardware Target (ADTC 2026 Standard Laptop)

| Spec | Value |
|------|-------|
| CPU | Intel Core i5 10th–12th gen |
| RAM | 8 GB DDR4 |
| Storage | 256 GB SSD |
| GPU | None (integrated graphics only) |
| OS | Ubuntu 22.04 LTS |
| Internet | Not required |

---

## Installation

### Step 1 — Clone the repository

```bash
git clone https://github.com/JosephWalusimbi-eng/Aletheia.git
cd Aletheia
```

### Step 1b — Install Python 3.11 (Ubuntu 22.04 — required before Step 2)

Ubuntu 22.04 ships with Python 3.10 but the ADTC profiler requires Python 3.11.
The package names `python3.11-pip` and `python3.11-venv` are **not available**
directly — use the deadsnakes PPA instead:

```bash
# Add deadsnakes PPA
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update

# Install Python 3.11
sudo apt install python3.11 python3.11-venv -y

# Install pip for 3.11 separately
curl -sS https://bootstrap.pypa.io/get-pip.py | sudo python3.11

# Set Python 3.11 as default
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo update-alternatives --set python3 /usr/bin/python3.11

# Verify — should show Python 3.11.x
python3 --version
```

> **On Ubuntu 24.04 and 26.04 this will not work.** deadsnakes publishes no 3.11
> build for 26.04, so `apt install python3.11` fails outright. Use the `uv` route in
> [SETUP_AND_TESTING.md](../SETUP_AND_TESTING.md) instead — it installs a
> self-contained CPython 3.11 into your home directory and needs no `sudo`.

### Step 2 — Run the install script

```bash
bash install.sh
```

This will automatically:
- Install all system dependencies (cmake, build-essential, python3-pip)
- Install Python packages (rich)
- Clone and build llama.cpp for CPU-only inference
- Write the inference configuration file

> ⏱ Takes approximately 3–5 minutes on first run.

### Step 3 — Download the model

```bash
bash download_model.sh
```

This downloads `aletheia_q4km.gguf` (~1.80 GB) — the primary deployment model.

> If automatic download fails, see
> [SETUP_AND_TESTING.md](../SETUP_AND_TESTING.md) for manual download instructions.

---

## Running Aletheia

Aletheia has three ways to run — choose whichever suits your workflow.

---

### Option 1 — Web UI (Recommended)

The web interface runs in your browser and walks through all three stages in order.

```bash
bash start_aletheia.sh          # starts the server and opens the browser
```

Or start the server directly:

```bash
python3 aletheia/server.py
```

Either way the interface is at **http://localhost:7860**.

**What the web UI looks like:**

```
+-----------------------------------------------------------------+
|  Aletheia Diagnostic AI                                         |
|  Offline clinical decision support for district hospitals       |
|  Fully offline. No internet required.                           |
+-----------------------------------------------------------------+
|  Advisory only. Aletheia does not diagnose and does not         |
|  prescribe. The treating clinician decides.                     |
+-----------------------------------------------------------------+
|  PATIENT PRESENTATION                                           |
|  Symptoms (separated by commas)                                 |
|  [ fever, headache, neck stiffness, vomiting                 ]  |
|  Duration (days) [ 2 ]   Age group [adult v]   Sex [unknown v]  |
|  Example cases:  (Meningitis) (Cerebral malaria) (Pulmonary TB) |
|                  (Eclampsia) (Postpartum haemorrhage) ...       |
+-----------------------------------------------------------------+
|  STEP 1  Assess presentation and generate follow-up questions   |
|  [        Run Step 1: Assess symptoms                        ]  |
|  Follow-up questions (answer all)  |  Tentative differential    |
|  Red flags                         |  Clinical rationale        |
+-----------------------------------------------------------------+
|  STEP 2  Answer the follow-up questions, get investigations     |
|  Answers to follow-up questions [                            ]  |
|  [   Run Step 2: Get investigation recommendations           ]  |
|      locked until Step 1 completes                              |
|  Recommended investigations        |  Working differential      |
|  Rationale for investigation selection                          |
+-----------------------------------------------------------------+
|  STEP 3  Enter investigation results, get clinical advisory     |
|  Investigation results [                                     ]  |
|  [   Run Step 3: Get clinical advisory                       ]  |
|      locked until Step 2 completes                              |
|  Clinical advisory                                              |
+-----------------------------------------------------------------+
```

**How to use the web UI:**

1. Type symptoms in the **Symptoms** box, separated by commas.
   Example: `fever, headache, neck stiffness, vomiting`
2. Set **Duration (days)**, **Age group**, and **Sex**.
3. Click **Run Step 1: Assess symptoms**. Aletheia returns the follow-up questions
   to ask, a tentative differential for context, red flags, and its clinical
   rationale. No investigations are suggested yet, by design.
4. Answer the follow-up questions in **Answers to follow-up questions**, then click
   **Run Step 2: Get investigation recommendations**. Aletheia returns the
   investigations to perform in priority order, plus the working differential.
5. Perform those investigations. Aletheia does not simulate them.
6. Enter the real findings in **Investigation results** and click
   **Run Step 3: Get clinical advisory** for the likely diagnosis, confidence,
   management options, and a suggested first step.

There is no task selector. Severity, red flags and the differential are all part of
the Step 1 output. Steps 2 and 3 stay dimmed and disabled until the preceding stage
completes, so the stages cannot be skipped.

**Or click an example case.** The chips sit directly beneath the input fields and
fill them in with one click (meningitis, cerebral malaria, pulmonary TB, eclampsia,
postpartum haemorrhage, severe malnutrition, snake envenomation).

> Each stage takes roughly 40 to 60 seconds on an i5-class CPU. A live counter shows
> the elapsed seconds while the model is working, and the button is disabled until it
> finishes. This is expected, not a hang.

To stop the web UI: press `Ctrl+C` in the terminal.

---

### Option 2 — Interactive Terminal Chatbot

A guided session-based chatbot in the terminal.

```bash
python3 cli.py
```

The chatbot will prompt you for:
- Symptoms (enter one per line, blank line to finish)
- Duration in days
- Age group (select by number)
- Sex
- Clinical reasoning task (select by number)

Then it displays the results with colour-coded severity and formatted tables.

Type `quit` or `exit` at any symptom prompt to end the session.
At the end of each case it asks if you want to assess another patient.

**Example session:**

```
╔══════════════════════════════════════════════════════════════╗
║   ALETHEIA Diagnostic AI                                     ║
║   Offline Clinical Decision Support · Soroti University, UG  ║
╚══════════════════════════════════════════════════════════════╝

─── Case 1 ───

PATIENT PRESENTATION
──────────────────────────────────────────────────────
  Symptom 1: fever
  Symptom 2: headache
  Symptom 3: neck stiffness
  Symptom 4: 
  Duration (days): 2
  Age group [5]: 5
  Sex (m/f): unknown

CLINICAL REASONING TASK:
  [1] Differential diagnosis (default)
  [2] Investigation recommendations
  ...
Select task: 1

Running inference...

[8.3s]

══════════════════ ALETHEIA ASSESSMENT ══════════════════

  Ranked Differential Diagnosis
  ┌──────┬─────────────────────────┬─────────────┬──────────┐
  │ Rank │ Condition               │ Probability │ Severity │
  ├──────┼─────────────────────────┼─────────────┼──────────┤
  │  1   │ Bacterial Meningitis    │ 55%  ██████ │ Critical │
  │  2   │ Viral Meningitis        │ 20%  ██     │ High     │
  │  3   │ Cerebral Malaria        │ 15%  █      │ Critical │
  │  4   │ Severe Typhoid          │  5%          │ High     │
  └──────┴─────────────────────────┴─────────────┴──────────┘

  PRIORITY INVESTIGATIONS:
  1. Lumbar puncture + CSF analysis
  2. Blood cultures x2 (before antibiotics)
  3. Malaria RDT STAT
  4. CBC differential
  5. Blood glucose

  ⚠  RED FLAGS:
  ▸ Petechial rash
  ▸ GCS dropping
  ▸ Focal neurology

  CLINICAL RATIONALE:
  Neck stiffness with fever is meningism until proven
  otherwise. LP is the diagnostic cornerstone. Start
  antibiotics within 1 hour even before LP result.

Assess another patient? [y/n]:
```

---

### Option 3 — Single Query (Command Line)

For scripting, automation, or quick one-off queries.

```bash
python3 run.py --symptoms "fever, headache, neck stiffness" --duration 2
```

**Full options:**

```bash
python3 run.py \
  --symptoms "altered consciousness, seizures, fever" \
  --duration 2 \
  --age child \
  --sex female \
  --stage initial_with_followup
```

```bash
python3 run.py --help
```

**Available stages** (`--stage`):

| Stage | Description | Requires `--extra` |
|-------|-------------|--------------------|
| `initial_with_followup` | Follow-up questions, tentative differential, red flags (default) | no |
| `test_recommendation` | Investigation priorities | yes — the follow-up answers |
| `advisory_conclusion` | Management advisory | yes — the investigation results |

Severity, red flags and the differential are all part of the Stage 1 output — they
are not separate stages.

**All flags:**

| Flag | Description |
|------|-------------|
| `--symptoms`, `-s` | Comma-separated symptoms (required) |
| `--duration`, `-d` | Duration in days (default: 1) |
| `--age` | `neonate`, `infant`, `child`, `adolescent`, `adult`, `elderly` |
| `--sex` | `male`, `female`, `unknown` |
| `--stage` | Pipeline stage, as above |
| `--extra` | Context for stages 2 and 3 |
| `--json` | Emit the raw JSON response |
| `--timeout` | Inference timeout in seconds (default: 600) |

**Get JSON output:**

```bash
python3 run.py --symptoms "chest pain, sweating, arm pain" --duration 1 --json
```

---

## Example Clinical Queries

```bash
# Bacterial meningitis vs cerebral malaria
python3 run.py --symptoms "fever, neck stiffness, headache, altered consciousness" --duration 2 --age adult

# Eclampsia — Stage 1 also returns severity and red flags
python3 run.py --symptoms "seizures, severe headache, high blood pressure, oedema" --duration 1 --age adult --sex female

# Severe acute malnutrition
python3 run.py --symptoms "severe wasting, oedema, anorexia, hair changes" --duration 90 --age child

# Snake envenomation — red flags come back in the Stage 1 output
python3 run.py --symptoms "bite wound, local swelling, coagulopathy signs, ptosis" --duration 0

# Pulmonary TB — Stage 2 needs the Stage 1 follow-up answers in --extra
python3 run.py --symptoms "cough, weight loss, night sweats, haemoptysis" --duration 30 \
    --stage test_recommendation \
    --extra "Known TB contact, no previous TB treatment, HIV status unknown"

# Postpartum haemorrhage — Stage 3 needs the investigation results in --extra
python3 run.py --symptoms "heavy bleeding after delivery, pallor, tachycardia" --duration 0 --sex female \
    --stage advisory_conclusion \
    --extra "Hb 6.2 g/dL, uterus atonic, no cervical tear on inspection, BP 80/50"
```

> `run.py` takes `--stage`, not `--task`. The valid stages are
> `initial_with_followup` (default), `test_recommendation`, and
> `advisory_conclusion`; the latter two require `--extra`. See `python3 run.py --help`.

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Top-1 Diagnostic Accuracy | **80.0%** |
| Top-3 Diagnostic Accuracy | **100.0%** |
| ROUGE-1 | 0.383 |
| BERTScore-F1 | **0.909** |
| METEOR | 0.467 |
| ECE (Calibration) | 0.275 |
| Training Loss (final) | 0.5197 |
| Training Time (A100) | 1.92 hours |
| Tokens per second (ADTC profiler) | **5.68 t/s** |
| Tokens per second (tuned, 4 threads) | **7.10 t/s** |
| First token latency (512-token prompt) | 30.0 s |
| Peak RAM (ADTC profiler) | **3,281 MB** |
| Steady-state RAM | 3,121 MB |
| ADTC Memory Ceiling | 7,168 MB |
| Margin | 3,887 MB |
| **ADTC Status** | ✅ **PASS** |

Runtime figures are from the ADTC profiler on an Intel Core i5-8350U; see
[REPORT.md](../REPORT.md) for the full environment. Accuracy figures are from our own
3,000-sample held-out evaluation, not the profiler.

---

## Clinical Conditions Covered (50)

**Infectious / Tropical (12):**
Cerebral Malaria · Uncomplicated Malaria · Bacterial Meningitis ·
Pulmonary Tuberculosis · HIV/AIDS with Opportunistic Infection ·
Typhoid Fever · Cholera · Viral Hepatitis B · Schistosomiasis ·
Visceral Leishmaniasis · Brucellosis · Meningococcal Meningitis

**Respiratory (3):**
Community-acquired Pneumonia · Asthma Exacerbation · Pleural Effusion

**Cardiovascular (3):**
Acute Myocardial Infarction · Hypertensive Emergency · Rheumatic Heart Disease

**Obstetric / Gynaecological (4):**
Eclampsia · Postpartum Haemorrhage · Ectopic Pregnancy · Puerperal Sepsis

**Paediatric (4):**
Severe Acute Malnutrition · Neonatal Sepsis · Paediatric Pneumonia ·
Sickle Cell Crisis

**Neurological (2):**
Epilepsy / Status Epilepticus · Ischaemic Stroke

**Renal / Endocrine (4):**
Acute Kidney Injury · Nephrotic Syndrome · Diabetic Ketoacidosis · Hypoglycaemia

**Surgical / Trauma (3):**
Snake Envenomation · Burns · Road Traffic Accident / Polytrauma

**Other (15):**
Septic Arthritis · Osteomyelitis · Trachoma · Leprosy · Buruli Ulcer ·
Kaposi Sarcoma · First Episode Psychosis · Alcohol Withdrawal ·
Otitis Media with Mastoiditis · Peritonsillar Abscess · Urethral Discharge STI ·
Malaria in Pregnancy · Urinary Tract Infection · Nephrotic Syndrome ·
Severe Malarial Anaemia

---

## Repository Structure

```
Aletheia/
├── README.md                  ← Project overview
├── SETUP_AND_TESTING.md       ← Full setup and testing guide
├── REPORT.md                  ← Technical report
├── LICENSE
├── metadata.json              ← ADTC submission descriptor
├── requirements.txt           ← Python dependencies
├── install.sh                 ← System dependencies + llama.cpp build
├── setup_venv.sh              ← Python 3.11 virtual environment setup
├── download_model.sh          ← Automated model download
├── start_aletheia.sh          ← Launcher (starts the web UI + browser)
├── run.py                     ← Single-stage CLI
├── cli.py                     ← Interactive terminal (all three stages)
├── aletheia/
│   ├── README.md              ← This file
│   ├── server.py              ← Web UI server ← START HERE
│   └── ui/index.html          ← Web UI page (self-contained)
├── inference/
│   ├── __init__.py
│   └── aletheia.py            ← Core inference wrapper
├── benchmark/
│   ├── benchmark.sh           ← Custom compliance benchmark
│   ├── run_adtc_profiler.sh   ← Official ADTC profiler runner
│   ├── results.json           ← Output of benchmark.sh
│   └── submission.json        ← Output of the ADTC profiler
├── docs/                      ← Paper, video script, setup guides
├── report/
│   └── ADTC_report.md         ← ADTC 2026 submission report
└── model/                     ← GGUF model, created by download_model.sh, gitignored
```

---

## Model Details

| Property | Value |
|----------|-------|
| Base model | Qwen2.5-3B-Instruct |
| Fine-tuning method | QLoRA (r=32, α=64) |
| Target modules | q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj |
| Trainable parameters | 59,867,136 (1.94%) |
| Training dataset | 27,000 samples |
| Training epochs | 3 |
| Training hardware | NVIDIA A100-SXM4-80GB |
| Training time | 1.92 hours |
| Deployment format | GGUF Q4_K_M |
| Model file size | 1.80 GB |
| Inference engine | llama.cpp (CPU only, no GPU) |

---

## ADTC 2026 Compliance

| Requirement | Value | Limit | Status |
|-------------|-------|-------|--------|
| Peak RAM | 3,281 MB | 7,168 MB | ✅ PASS (3,887 MB margin) |
| Internet at runtime | None | None | ✅ PASS |
| GPU at runtime | None | None | ✅ PASS |
| African use case | Healthcare, Uganda | Bonus +10 pts | ✅ YES |

---

## Running the Benchmark

Aletheia supports both the **official ADTC profiler** and a custom benchmark script.

---

### Option A — Official ADTC Profiler (Required for submission)

The official profiler from the Africa Deep Tech Foundation measures latency,
throughput, memory, and CPU performance in a standardised way that matches
what judges use to evaluate your submission.

```bash
bash benchmark/run_adtc_profiler.sh
```

This script will:
1. Install the official profiler from [github.com/Africa-Deep-Tech-Foundation/adtc-profiler](https://github.com/Africa-Deep-Tech-Foundation/adtc-profiler)
2. Check prerequisites (Python ≥ 3.11, `llama-bench`, the model file)
3. Run it against `aletheia_q4km.gguf` in participant mode
4. Save results to `benchmark/submission.json`

**Use the numbers from this output for the ADTC Self-Reported Profiler Score
on your Devpost submission form.**

You can also run the profiler manually:

```bash
# Install the profiler (it ships as a pip package, not a script to clone)
pip3 install "git+https://github.com/Africa-Deep-Tech-Foundation/adtc-profiler.git"

# Run it against this submission directory — it reads the model path
# and test prompts from metadata.json
adtc-profiler run \
    --submission . \
    --mode participant \
    --output benchmark/submission.json \
    --skip-accuracy
```

> `llama-bench` must be on your `PATH` (it is built alongside `llama-cli`):
> `export PATH="$HOME/llama.cpp/build/bin:$PATH"`

---

### Option B — Custom Benchmark Script

For quick local testing and sanity checks:

```bash
bash benchmark/benchmark.sh
```

Results are saved to `benchmark/results.json`.
This script measures the same metrics but uses a simpler implementation.
**Do not use these numbers for the official ADTC submission — use Option A.**

---

## Citation

If you use Aletheia in your research, please cite:

```bibtex
@article{walusimbi2026aletheia,
  title   = {Aletheia: An Offline-First Clinical Decision Support System
             for Low-Resource Healthcare Settings in Sub-Saharan Africa},
  author  = {Walusimbi, Joseph and Oguti, Ann Move and
             Sserwadda, Abubakhari and Nasasara, Precious},
  journal = {IEEE Journal of Biomedical and Health Informatics},
  year    = {2026},
  note    = {Under review}
}
```

---

## Team

**Soroti University, Uganda**

| Name | Department |
|------|-----------|
| Joseph Walusimbi | Electronics & Computer Engineering |
| Ann Move Oguti | Electronics & Computer Engineering |
| Abubakhari Sserwadda | Electronics & Computer Engineering |
| Precious Nasasara | School of Health Sciences |

**Arapai Technologies International Limited** — Uganda

---

## Conflict of Interest

J. Walusimbi is the founder and director of Arapai Technologies
International Limited. Aletheia is intended for future commercialisation
through this entity.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

> *Aletheia is a research prototype. It is not a licensed medical device
> and should not be used as the sole basis for clinical decisions.
> All outputs must be reviewed by a qualified healthcare professional.*
