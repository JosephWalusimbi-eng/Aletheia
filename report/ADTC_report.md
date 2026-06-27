# Aletheia — ADTC 2026 Project Report

**Africa Deep Tech Challenge 2026 | Laptop LLM Track**

---

## 1. Problem Definition

### Context
In Uganda, the physician-to-patient ratio is approximately 1:25,000 — among
the lowest in the world. At district hospitals and health centres, a single
clinical officer may conduct 80–120 consultations per day, leaving fewer than
five minutes per patient for history-taking, examination, differential
diagnosis, and management planning.

Existing AI-assisted clinical decision support systems (CDSS) require:
- Persistent internet connectivity (unavailable or unreliable in rural Uganda)
- Cloud-based inference infrastructure (unaffordable at primary care level)
- High-specification hardware (not present at district facilities)

This creates a paradox: the populations that most need diagnostic support
have the least access to the tools designed to provide it.

### Problem Statement
Design and deploy a clinically useful AI diagnostic reasoning system that
runs entirely offline on commodity laptop hardware, covering the disease
conditions most commonly encountered at district health facilities in
sub-Saharan Africa.

---

## 2. Identified Constraints

| Constraint | Value | Source |
|------------|-------|--------|
| Maximum RAM | 7,168 MB | ADTC 2026 standard |
| CPU | Intel Core i5 10–12th gen | ADTC 2026 standard |
| GPU | None (integrated only) | ADTC 2026 standard |
| OS | Ubuntu 22.04 LTS | ADTC 2026 standard |
| Internet | None at inference | Design requirement |
| Model size | < 4 GB | Practical deployment |
| Inference latency | < 30 seconds | Clinical usability |
| Languages | English | v1.0 scope |

---

## 3. Design Alternatives and Decisions

### Model Selection

| Option | Parameters | RAM | Quality | Decision |
|--------|-----------|-----|---------|----------|
| Qwen2.5-0.5B | 0.5B | ~0.8 GB | Too limited | Rejected |
| Qwen2.5-1.5B | 1.5B | ~1.5 GB | Limited reasoning | Rejected |
| **Qwen2.5-3B** | **3.09B** | **~3.6 GB** | **Strong** | **✅ Selected** |
| Llama-3.2-3B | 3.2B | ~3.9 GB | Good | Alternative |
| Qwen2.5-7B | 7.4B | ~8.5 GB | Exceeds budget | Rejected |

### Fine-tuning Method

| Option | Memory | Quality | Decision |
|--------|--------|---------|----------|
| Full fine-tuning | >40 GB VRAM | Best | Impractical |
| LoRA (full precision) | ~20 GB VRAM | Very good | Requires A100 |
| **QLoRA (4-bit)** | **~6 GB VRAM** | **Good** | **✅ Selected** |
| Prompt engineering only | 0 | Limited | Insufficient |

### Quantisation Format

| Format | Size | RAM | Quality loss | Decision |
|--------|------|-----|--------------|----------|
| F16 | 6.18 GB | ~8 GB | None | Exceeds budget |
| Q8_0 | 3.2 GB | ~5 GB | <1% | Acceptable |
| **Q4_K_M** | **1.80 GB** | **~3.6 GB** | **~2%** | **✅ Selected** |
| Q2_K | 1.19 GB | ~3.0 GB | ~8% | Fallback |

Q4_K_M provides approximately 98% of F16 quality at 29% of the file
size, well within the ADTC memory ceiling with 3,538 MB to spare.

### Interface

| Option | RAM overhead | Decision |
|--------|-------------|----------|
| Terminal CLI only | ~0 MB | Available |
| **Gradio Web UI** | **~150 MB** | **✅ Selected (primary)** |
| Electron desktop app | ~400 MB | Future work |

### Inference Engine

| Option | CPU support | Performance | Decision |
|--------|------------|-------------|----------|
| **llama.cpp** | **✅ Excellent** | **Best CPU** | **✅ Selected** |
| Ollama | ✅ Good | Moderate | Alternative |
| HuggingFace transformers | ✅ Slow | Slow on CPU | Rejected |

---

## 4. Tools Used

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10 | Training and inference wrapper |
| PyTorch | 2.11.0 | Training backend |
| Transformers | 4.44.2 | Model loading and tokenisation |
| PEFT | 0.12.0 | QLoRA fine-tuning |
| TRL | 0.10.1 | SFT training loop |
| bitsandbytes | 0.43.0+ | 4-bit quantisation during training |
| llama.cpp | Latest | GGUF CPU inference |
| Gradio | 4.0+ | Web UI interface |
| Google Colab Pro | A100-SXM4-80GB | Training hardware |
| MedQA-USMLE | — | Training data source |
| MedMCQA | — | Training data source |

---

## 5. Dataset

**Total: 30,000 samples | Train: 27,000 | Eval: 3,000**

| Source | Samples | Proportion |
|--------|---------|------------|
| Aletheia-Synthetic | 18,000 | 60% |
| MedQA-USMLE | 6,000 | 20% |
| MedMCQA | 6,000 | 20% |

**Clinical conditions covered:** 50 conditions weighted for African
disease epidemiology across Infectious/Tropical, Respiratory,
Cardiovascular, Obstetric, Paediatric, Neurological, Renal/Endocrine,
Surgical/Trauma, and other specialties.

**Reasoning types:** 8 types — initial differential, test recommendation,
evidence update, rationale explanation, follow-up questions, severity
assessment, treatment hint, and red flag identification.

---

## 6. Performance Results

### Clinical Accuracy

| Metric | Value |
|--------|-------|
| Top-1 Diagnostic Accuracy | **80.0%** |
| Top-3 Diagnostic Accuracy | **100.0%** |

### Language Quality

| Metric | Value |
|--------|-------|
| ROUGE-1 (F1) | 0.383 |
| ROUGE-2 (F1) | 0.266 |
| ROUGE-L (F1) | 0.349 |
| BERTScore-F1 | **0.909** |
| METEOR | 0.467 |

### Calibration

| Metric | Value |
|--------|-------|
| ECE (Expected Calibration Error) | 0.275 |
| Training Loss (final) | 0.5197 |

### ADTC Compliance

| Metric | Value | ADTC Limit | Status |
|--------|-------|------------|--------|
| Model size (Q4_K_M) | **1.80 GB** | — | — |
| Model size (Q2_K fallback) | 1.19 GB | — | — |
| Peak RAM (Q4_K_M) | **~3,630 MB** | 7,168 MB | ✅ PASS |
| Peak RAM (Q2_K fallback) | ~2,990 MB | 7,168 MB | ✅ PASS |
| Margin below ceiling | 3,538 MB | — | ✅ |
| Internet required | None | None | ✅ |
| GPU required | None | None | ✅ |
| African use case | Healthcare, Uganda | +10 pts bonus | ✅ YES |

---

## 7. Training Details

| Parameter | Value |
|-----------|-------|
| Base model | Qwen2.5-3B-Instruct |
| LoRA rank (r) | 32 |
| LoRA alpha (α) | 64 |
| LoRA dropout | 0.05 |
| Trainable parameters | 59,867,136 (1.94%) |
| Target modules | q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj |
| Training epochs | 3 |
| Effective batch size | 16 |
| Learning rate | 2 × 10⁻⁴ |
| LR scheduler | Cosine with warmup (5%) |
| Training loss (final) | 0.5197 |
| Training time | 1.92 hours |
| Hardware | NVIDIA A100-SXM4-80GB (Google Colab Pro) |
| Precision | BFloat16 (full precision, no quantisation during training) |

---

## 8. African Use Case

**Domain:** Healthcare — Clinical Decision Support

**Target users:** Clinical officers, nurses, and physicians at district
hospitals and health centres across sub-Saharan Africa

**Deployment context:**
- District hospitals with no specialist physicians
- Rural health centres with intermittent electricity
- Facilities with no reliable internet connectivity
- Settings where a single clinical officer sees 80–120 patients/day

**Active clinical validation:** Two co-authors from the School of Health
Sciences, Soroti University — Precious Boss Kasasira and Charles Brian
Okoboi — are practising clinicians actively testing and evaluating
Aletheia against real clinical presentations. Early findings indicate the
ranked differential output is clinically plausible and useful for decision
support in the majority of cases reviewed to date.

**Impact:** A system that presents the correct diagnosis in 80% of
first suggestions and 100% of top-3 suggestions functions as a genuine
cognitive support tool that ensures critical conditions — meningitis,
eclampsia, cerebral malaria — are not missed under time pressure.

**ADTC African Use Case Bonus (+10 pts):** ✅ Yes — healthcare,
Uganda, district hospital deployment

---

## 9. Limitations

1. Training data predominantly synthetic — probability distributions
   reflect authors' clinical knowledge rather than empirical
   epidemiological data. Ongoing refinement with clinician co-authors.
2. Evaluation on 10 core case categories using automated metrics —
   broader clinician-graded evaluation set under development.
3. ECE of 0.275 — probability estimates should be treated as relative
   rankings rather than absolute confidence values.
4. Formal prospective validation study pending IRB approval — active
   informal evaluation currently underway with clinician co-authors.

---

## 10. Future Work

- Formal reporting of ongoing clinical evaluation with co-authors
- Multi-site prospective validation study across Eastern Uganda
  (target: 500+ cases, subject to UNCST IRB approval)
- Expansion from 50 to 100+ clinical conditions
- Kiswahili and Ateso language support
- Desktop GUI for non-technical clinical users
- Uganda NDA software-as-a-medical-device regulatory pathway
- Commercialisation through Arapai Technologies International Limited

---

## 11. Team

**Soroti University — Department of Electronics and Computer Engineering:**
- Joseph Walusimbi
- Ann Move Oguti
- Abubakhari Sserwadda

**Soroti University — School of Health Sciences:**
- Precious Boss Kasasira (practising clinician, validation co-author)
- Charles Brian Okoboi (practising clinician, validation co-author)

**Arapai Technologies International Limited, Uganda**

---

## 12. Repository

https://github.com/JosephWalusimbi-eng/Aletheia

---

*Aletheia is a research prototype. It is not a licensed medical device
and should not be used as the sole basis for clinical decisions.*
