# Aletheia — Offline-First Clinical Decision Support AI

> *From the Greek ἀλήθεια — truth, disclosure. The revealing of what is hidden.*

[![ADTC 2026](https://img.shields.io/badge/ADTC%202026-Laptop%20LLM%20Track-blue)](https://adtc-2026.devpost.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Model: Qwen2.5-3B](https://img.shields.io/badge/Model-Qwen2.5--3B--Instruct-orange)](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct)
[![RAM: ~3.9 GB](https://img.shields.io/badge/RAM-~3.9%20GB-brightgreen)](models/)
[![Offline](https://img.shields.io/badge/Internet-Not%20Required-success)](install.sh)

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
- ✅ **~3,880 MB peak RAM** — well within the 8 GB ADTC budget
- ✅ **Web UI + CLI** — browser interface or terminal
- ✅ **50 clinical conditions** weighted for African disease epidemiology
- ✅ **8 reasoning task types** — differential, tests, severity, management, red flags

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

### Step 2 — Run the install script

```bash
bash install.sh
```

This will automatically:
- Install all system dependencies (cmake, build-essential, python3-pip)
- Install Python packages (gradio, rich, requests)
- Clone and build llama.cpp for CPU-only inference
- Write the inference configuration file

> ⏱ Takes approximately 3–5 minutes on first run.

### Step 3 — Download the model

```bash
bash models/download_model.sh
```

This downloads `aletheia_q4km.gguf` (~1.80 GB) — the primary deployment model.

> If automatic download fails, see [models/README.md](models/README.md) for
> manual download instructions.

---

## Running Aletheia

Aletheia has three ways to run — choose whichever suits your workflow.

---

### Option 1 — Web UI (Recommended)

The web interface runs in your browser. Clean, visual, easy to use.

```bash
python3 app.py
```

Your browser will open automatically at **http://localhost:7860**

If it does not open automatically, navigate there manually.

**What the web UI looks like:**

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚕ Aletheia Diagnostic AI                                       │
│  Offline-first clinical decision support for sub-Saharan Africa │
│  🔒 Fully Offline — No Internet Required                        │
├─────────────────────────────┬───────────────────────────────────┤
│  PATIENT PRESENTATION       │  ASSESSMENT                       │
│                             │                                   │
│  Symptoms:                  │  🩺 Differential Diagnosis        │
│  [fever, headache, ...]     │  🔬 Investigations                │
│                             │  📋 Clinical Rationale            │
│  Duration: [slider]         │  ⚠️  Red Flags                   │
│  Age group: [dropdown]      │  ℹ️  Metadata                    │
│  Sex: [dropdown]            │                                   │
│  Task: [dropdown]           │                                   │
│                             │                                   │
│  [▶ Run Clinical Assessment]│                                   │
│                             │                                   │
│  Example Cases:             │                                   │
│  • Meningitis               │                                   │
│  • Cerebral Malaria         │                                   │
│  • Tuberculosis             │                                   │
│  • Eclampsia                │                                   │
│  • PPH                      │                                   │
└─────────────────────────────┴───────────────────────────────────┘
```

**How to use the web UI:**

1. Type symptoms in the **Symptoms** box, separated by commas
   - Example: `fever, headache, neck stiffness, vomiting`
2. Set the **Duration** slider to how many days symptoms have been present
3. Select the **Age Group** from the dropdown
4. Select the **Sex** if known
5. Choose the **Clinical Reasoning Task**:
   - **Differential Diagnosis** — ranked list of possible diagnoses
   - **Investigation Recommendations** — which tests to order first
   - **Severity & Level of Care** — how urgent is this case
   - **Immediate Management** — what to do right now
   - **Follow-up Questions** — what to ask next to narrow the diagnosis
   - **Red Flags Only** — immediate escalation triggers
6. Click **▶ Run Clinical Assessment**
7. Results appear in the tabs on the right

**Or click any Example Case** to load a pre-filled presentation instantly.

To stop the web UI: press `Ctrl+C` in the terminal.

---

### Option 2 — Interactive Terminal Chatbot

A guided session-based chatbot in the terminal.

```bash
python3 chat/cli.py
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
  --task severity_assessment
```

```bash
python3 run.py --help
```

**Available tasks:**

| Task flag | Description |
|-----------|-------------|
| `initial_differential` | Ranked differential diagnosis (default) |
| `test_recommendation` | Investigation priorities |
| `severity_assessment` | Severity and level of care |
| `treatment_hint` | Immediate management |
| `follow_up_questions` | Diagnostic follow-up questions |
| `red_flag_identification` | Immediate escalation triggers |

**Get JSON output:**

```bash
python3 run.py --symptoms "chest pain, sweating, arm pain" --duration 1 --json
```

---

## Example Clinical Queries

```bash
# Bacterial meningitis vs cerebral malaria
python3 run.py --symptoms "fever, neck stiffness, headache, altered consciousness" --duration 2 --age adult

# Eclampsia
python3 run.py --symptoms "seizures, severe headache, high blood pressure, oedema" --duration 1 --age adult --sex female --task severity_assessment

# Severe acute malnutrition
python3 run.py --symptoms "severe wasting, oedema, anorexia, hair changes" --duration 90 --age child --task immediate_management

# Pulmonary TB
python3 run.py --symptoms "cough, weight loss, night sweats, haemoptysis" --duration 30 --task test_recommendation

# Snake envenomation
python3 run.py --symptoms "bite wound, local swelling, coagulopathy signs, ptosis" --duration 0 --task red_flag_identification

# Postpartum haemorrhage
python3 run.py --symptoms "heavy bleeding after delivery, pallor, tachycardia" --duration 0 --sex female --task treatment_hint
```

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
| Peak RAM — CLI | ~3,630 MB |
| Peak RAM — Web UI | ~3,880 MB |
| ADTC Memory Ceiling | 7,168 MB |
| **ADTC Status** | ✅ **PASS** |

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
├── README.md                  ← This file
├── app.py                     ← Web UI (Gradio) ← START HERE
├── install.sh                 ← One-command Ubuntu 22.04 setup
├── run.py                     ← Single-query CLI
├── requirements.txt           ← Python dependencies
├── LICENSE
├── chat/
│   ├── __init__.py
│   └── cli.py                 ← Interactive terminal chatbot
├── inference/
│   ├── __init__.py
│   └── aletheia.py            ← Core inference wrapper
├── models/
│   ├── README.md              ← Model download instructions
│   └── download_model.sh      ← Automated model download
├── benchmark/
│   └── benchmark.sh           ← ADTC compliance benchmark
└── report/
    └── ADTC_report.md         ← ADTC 2026 submission report
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
| Peak RAM (Web UI) | ~3,880 MB | 7,168 MB | ✅ PASS |
| Peak RAM (CLI) | ~3,630 MB | 7,168 MB | ✅ PASS |
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
1. Clone the official profiler from [github.com/Africa-Deep-Tech-Foundation/adtc-profiler](https://github.com/Africa-Deep-Tech-Foundation/adtc-profiler)
2. Install its dependencies
3. Run it against `aletheia_q4km.gguf`
4. Save results to `benchmark/adtc_profiler_results.json`

**Use the numbers from this output for the ADTC Self-Reported Profiler Score
on your Devpost submission form.**

You can also run the profiler manually:

```bash
# Clone profiler
git clone https://github.com/Africa-Deep-Tech-Foundation/adtc-profiler.git
cd adtc-profiler

# Install dependencies
pip3 install -r requirements.txt

# Run against Aletheia model
python3 profiler.py --model ../models/aletheia_q4km.gguf
```

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
