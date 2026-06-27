# Aletheia — Offline-First Clinical Decision Support AI

> *From the Greek ἀλήθεια — truth, disclosure. The revealing of what is hidden.*

[![ADTC 2026](https://img.shields.io/badge/ADTC%202026-Laptop%20LLM%20Track-blue)](https://adtc-2026.devpost.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Model: Qwen2.5-3B](https://img.shields.io/badge/Model-Qwen2.5--3B--Instruct-orange)](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct)
[![RAM: ~3.7 GB](https://img.shields.io/badge/RAM-~3.7%20GB-brightgreen)](models/)

**Aletheia** is an offline-first clinical decision support system designed for frontline
healthcare workers in district hospitals and health centres across Africa.
It runs entirely on a standard 8 GB laptop with no internet connection,
providing ranked differential diagnoses, investigation recommendations,
and clinical reasoning for 50 disease conditions prevalent across sub-Saharan Africa.

---

## The Problem

In Uganda, one doctor serves approximately 25,000 patients.
A clinical officer at a district hospital may see 100 patients in a single day —
fewer than 5 minutes per patient — to take a history, examine, diagnose, and treat.
Existing AI diagnostic tools require cloud servers, fast internet, and expensive hardware.
None of these are reliably available at the point of care in rural Africa.

## The Solution

Aletheia runs the entire clinical reasoning pipeline **on-device**:

- **No internet required** — ever
- **No GPU required** — runs on CPU only
- **1.93 GB model file** — fits on any laptop
- **~3,730 MB peak RAM** — well within the 8 GB ADTC budget
- **Under 10 seconds per query** on the target hardware
- **50 clinical conditions** weighted for African disease epidemiology

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

## Quick Start

### 1. Install (Ubuntu 22.04)

```bash
git clone https://github.com/JosephWalusimbi-eng/Aletheia.git
cd Aletheia
bash install.sh
```

This installs all dependencies and builds the inference engine automatically.

### 2. Download the Model

```bash
bash models/download_model.sh
```

This downloads `aletheia_q4km.gguf` (~1.93 GB) from Google Drive.

### 3. Run the Chatbot

```bash
python3 chat/cli.py
```

Or for a single query:

```bash
python3 run.py --symptoms "fever, headache, neck stiffness" --duration 2
```

---

## Example Output

```
=== ALETHEIA DIAGNOSTIC AI ===
Symptoms : fever, headache, neck stiffness
Duration : 2 days

RANKED DIFFERENTIAL DIAGNOSIS:
1. Bacterial Meningitis     55%  [CRITICAL]
2. Viral Meningitis         20%  [HIGH]
3. Cerebral Malaria         15%  [CRITICAL]
4. Severe Typhoid            5%  [HIGH]

PRIORITY INVESTIGATIONS:
1. Lumbar puncture + CSF analysis
2. Blood cultures x2 (before antibiotics)
3. Malaria RDT STAT
4. CBC differential
5. Blood glucose

RED FLAGS:
⚠  Petechial rash (meningococcal sepsis)
⚠  GCS dropping
⚠  Focal neurology

CLINICAL RATIONALE:
Neck stiffness with fever is meningism until proven otherwise.
LP is the diagnostic cornerstone. Start antibiotics within
1 hour of clinical diagnosis even before LP result.

FOLLOW-UP QUESTIONS:
1. Kernig and Brudzinski signs?
2. Petechial or purpuric rash?
3. Immunocompromised (HIV, steroids)?
4. Recent ear or sinus infection?
```

---

## Clinical Conditions Covered (50)

**Infectious / Tropical (12):** Cerebral Malaria, Uncomplicated Malaria,
Bacterial Meningitis, Pulmonary TB, HIV/AIDS with OI, Typhoid Fever,
Cholera, Viral Hepatitis B, Schistosomiasis, Visceral Leishmaniasis,
Brucellosis, Meningococcal Meningitis

**Respiratory (3):** Community-acquired Pneumonia, Asthma Exacerbation,
Pleural Effusion

**Cardiovascular (3):** Acute Myocardial Infarction, Hypertensive Emergency,
Rheumatic Heart Disease

**Obstetric / Gynaecological (4):** Eclampsia, Postpartum Haemorrhage,
Ectopic Pregnancy, Puerperal Sepsis

**Paediatric (4):** Severe Acute Malnutrition, Neonatal Sepsis,
Paediatric Pneumonia, Sickle Cell Crisis

**Neurological (2):** Epilepsy / Status Epilepticus, Ischaemic Stroke

**Renal / Endocrine (4):** Acute Kidney Injury, Nephrotic Syndrome,
Diabetic Ketoacidosis, Hypoglycaemia

**Surgical / Trauma (3):** Snake Envenomation, Burns, Road Traffic Accident

**Other (15):** Septic Arthritis, Osteomyelitis, Trachoma, Leprosy,
Buruli Ulcer, Kaposi Sarcoma, First Episode Psychosis, Alcohol Withdrawal,
Otitis Media with Mastoiditis, Peritonsillar Abscess, Urethral Discharge STI,
Malaria in Pregnancy, UTI, Nephrotic Syndrome, Severe Malarial Anaemia

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Top-1 Diagnostic Accuracy | 80.0% |
| Top-3 Diagnostic Accuracy | 100.0% |
| ROUGE-1 | 0.383 |
| BERTScore-F1 | 0.909 |
| METEOR | 0.467 |
| ECE (Calibration) | 0.275 |
| Training Loss | 0.5197 |
| Training Time (A100) | 1.92 hours |
| Peak RAM (Q4_K_M) | ~3,730 MB |
| ADTC Memory Ceiling | 7,168 MB |
| **ADTC Status** |  PASS |

---

## Model Details

| Property | Value |
|----------|-------|
| Base model | Qwen2.5-3B-Instruct |
| Fine-tuning method | QLoRA (r=32, α=64) |
| Trainable parameters | 59,867,136 (1.94%) |
| Training dataset | 27,000 samples (50 conditions, 8 reasoning types) |
| Deployment format | GGUF Q4_K_M |
| Model size | 1.93 GB |
| Inference engine | llama.cpp (CPU, no GPU) |

---

## Repository Structure

```
Aletheia/
├── README.md                  ← This file
├── install.sh                 ← One-command Ubuntu 22.04 setup
├── run.py                     ← Single-query inference
├── LICENSE
├── requirements.txt
├── chat/
│   └── cli.py                 ← Interactive terminal chatbot
├── inference/
│   └── aletheia.py            ← Core inference wrapper
├── models/
│   ├── README.md              ← Model download instructions
│   └── download_model.sh      ← Download GGUF from Drive
├── benchmark/
│   └── benchmark.sh           ← ADTC compliance benchmark
├── report/
│   └── ADTC_report.md         ← ADTC submission report
└── docs/
    └── clinical_conditions.md ← Full condition reference
```

---

## Training

Training was performed on Google Colab Pro (NVIDIA A100-SXM4-80GB).
The full training pipeline is documented in `Arapai_Colab_ADTC.ipynb`
available on request.

**Dataset sources:**
- Aletheia-Synthetic: 18,000 Africa-weighted clinical reasoning samples
- MedQA-USMLE: 6,000 filtered questions
- MedMCQA: 6,000 filtered questions

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

- Joseph Walusimbi — Dept. of Electronics and Computer Engineering
- Ann Move Oguti — Dept. of Electronics and Computer Engineering
- Abubakhari Sserwadda — Dept. of Electronics and Computer Engineering
- Precious Nasasara — School of Health Sciences

**Arapai Technologies International Limited** — Uganda

---

## Conflict of Interest

J. Walusimbi is the founder and director of Arapai Technologies
International Limited. Aletheia is intended for future
commercialisation through this entity.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

*Aletheia is a research prototype. It is not a licensed medical device
and should not be used as the sole basis for clinical decisions.*