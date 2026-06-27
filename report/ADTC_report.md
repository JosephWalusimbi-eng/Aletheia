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
| **Qwen2.5-3B** | **3.09B** | **~3.7 GB** | **Strong** | **✅ Selected** |
| Llama-3.2-3B | 3.2B | ~3.9 GB | Good | Alternative |
| Qwen2.5-7B | 7.4B | ~8.5 GB | Exceeds budget | Rejected |

Qwen2.5-3B-Instruct was selected for its strong instruction-following
performance at a parameter count that fits comfortably within the ADTC
memory budget after Q4_K_M quantisation.

### Fine-tuning Method

| Option | Memory | Quality | Decision |
|--------|--------|---------|----------|
| Full fine-tuning | >40 GB VRAM | Best | Impractical |
| LoRA (full precision) | ~20 GB VRAM | Very good | Requires A100 |
| **QLoRA (4-bit)** | **~6 GB VRAM** | **Good** | **✅ Selected** |
| Prompt engineering only | 0 | Limited | Insufficient |

QLoRA with r=32, α=64 on all 7 linear projection layers provided
an optimal balance between training quality and compute cost.

### Quantisation Format

| Format | Size | RAM | Quality loss | Decision |
|--------|------|-----|--------------|----------|
| F16 | 6.18 GB | ~8 GB | None | Exceeds budget |
| Q8_0 | 3.2 GB | ~5 GB | <1% | Acceptable |
| **Q4_K_M** | **1.93 GB** | **~3.7 GB** | **~2%** | **✅ Selected** |
| Q2_K | 1.27 GB | ~3.1 GB | ~8% | Fallback |

Q4_K_M provides approximately 98% of F16 quality at 31% of the file
size, well within the ADTC memory ceiling with 3,438 MB to spare.

### Inference Engine

| Option | CPU support | Performance | Decision |
|--------|------------|-------------|----------|
| **llama.cpp** | **✅ Excellent** | **Best CPU** | **✅ Selected** |
| Ollama | ✅ Good | Moderate | Alternative |
| HuggingFace transformers | ✅ Slow | Slow on CPU | Rejected |
| ONNX Runtime | ✅ Good | Moderate | Alternative |

llama.cpp was selected for its superior CPU inference performance,
minimal dependencies, and native GGUF format support.

---

## 4. Tools Used

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10 | Training and inference wrapper |
| PyTorch | 2.11.0 | Training backend |
| Transformers | 4.44.2 | Model loading and tokenisation |
| PEFT | 0.12.0 | QLoRA fine-tuning |
| TRL | 0.10.1 | SFT training loop |
| bitsandbytes | 0.43.0+ | 4-bit quantisation |
| llama.cpp | Latest | GGUF CPU inference |
| Google Colab Pro | A100 | Training hardware |
| MedQA-USMLE | - | Training data (real MCQs) |
| MedMCQA | - | Training data (real MCQs) |

---

## 5. Dataset

**Total training samples:** 27,000 (train: 24,300 / eval: 2,700)

| Source | Samples | Proportion |
|--------|---------|------------|
| Aletheia-Synthetic | 18,000 | 60% |
| MedQA-USMLE | 6,000 | 20% |
| MedMCQA | 6,000 | 20% |

**Clinical conditions covered:** 50 conditions weighted for African
disease epidemiology, spanning Infectious/Tropical, Respiratory,
Cardiovascular, Obstetric, Paediatric, Neurological, Renal/Endocrine,
Surgical/Trauma, and other specialties.

**Reasoning types:** 8 task types including initial differential,
test recommendation, evidence update, rationale explanation,
follow-up questions, severity assessment, treatment hint,
and red flag identification.

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
| MCE (Maximum Calibration Error) | — |
| Brier Score | — |

### ADTC Compliance

| Metric | Value | ADTC Limit | Status |
|--------|-------|------------|--------|
| Model file size | 1.93 GB | — | — |
| Estimated peak RAM | ~3,730 MB | 7,168 MB | ✅ PASS |
| Margin below ceiling | 3,438 MB | — | ✅ |
| Internet required | None | None | ✅ |
| GPU required | None | None | ✅ |

---

## 7. Training Details

| Parameter | Value |
|-----------|-------|
| Base model | Qwen2.5-3B-Instruct |
| LoRA rank (r) | 32 |
| LoRA alpha (α) | 64 |
| LoRA dropout | 0.05 |
| Trainable parameters | 59,867,136 (1.94%) |
| Training epochs | 3 |
| Effective batch size | 16 |
| Learning rate | 2 × 10⁻⁴ |
| LR scheduler | Cosine with warmup |
| Training loss (final) | 0.5197 |
| Training time | 1.92 hours (A100) |
| Precision | BFloat16 |

---

## 8. African Use Case

**Domain:** Healthcare — Clinical Decision Support

**Target users:** Clinical officers and nurses at district hospitals
and health centres across sub-Saharan Africa

**Deployment context:**
- District hospitals with no specialist physicians
- Rural health centres with intermittent electricity
- Facilities with no reliable internet connectivity
- Settings where a single clinical officer sees 80–120 patients/day

**Impact:** In a context where the correct diagnosis appears in the
top 3 suggestions 100% of the time, Aletheia functions as a cognitive
support tool that ensures critical conditions (meningitis, eclampsia,
cerebral malaria) are not missed under time pressure.

**Relevant to ADTC African Use Case Bonus (+10 pts):** ✅ Yes

---

## 9. Limitations

1. Training data is predominantly synthetic and has not been
   validated by practising Ugandan clinicians
2. Evaluation conducted on 10 core case categories — a larger
   clinician-validated evaluation set is needed
3. ECE of 0.275 indicates probability estimates need calibration
   before use as actionable confidence values
4. No prospective clinical validation study completed yet

---

## 10. Future Work

- Prospective clinical validation at multiple health facilities
  in Eastern Uganda (IRB pending)
- Expansion to 100+ clinical conditions
- Kiswahili and Ateso language support
- Lightweight desktop GUI for non-technical users
- Uganda NDA software-as-a-medical-device regulatory pathway

---

## 11. Team

**Soroti University, Uganda — Department of Electronics and
Computer Engineering:**
- Joseph Walusimbi
- Ann Move Oguti
- Abubakhari Sserwadda

**Soroti University — School of Health Sciences:**
- Precious Nasasara

**Arapai Technologies International Limited, Uganda**

---

## 12. Repository

https://github.com/JosephWalusimbi-eng/Aletheia

---

*Aletheia is a research prototype. It is not a licensed medical device.*
