# Aletheia - Technical Report
### ADTC 2026 Submission · Healthcare / Medical Track

---

## 1. Problem

District hospitals and rural health centres in sub-Saharan Africa handle a broad and severe case mix - meningitis, cerebral malaria, TB, obstetric emergencies, snakebite - often with a single clinician on duty, no specialist support, and unreliable or no internet connectivity. Clinical decision support tools that exist today assume a cloud connection and a general-purpose workstation. They are unusable at the point of care in these settings.

The result is that clinicians must reason through complex, overlapping differentials entirely from memory, with no structured second opinion available. Diagnostic delays and missed investigations are a direct consequence.

**Target user:** A clinician - clinical officer, nurse, or medical officer - working alone at a district hospital or health centre in Uganda or a similar East/Central African setting. They have a basic laptop and no reliable internet. They need structured reasoning support, not a remote consultation.

**What Aletheia does not claim:** It does not diagnose. It does not prescribe. It supports the clinician's reasoning through a three-stage pipeline that ends with an advisory output explicitly framed as the clinician's decision to make.

---

## 2. Design Decisions

### Pipeline structure

Aletheia enforces a three-stage clinical reasoning flow, in order:

1. **Stage 1: Initial assessment:** The model receives symptoms and patient demographics and returns a tentative differential plus 3–5 targeted follow-up questions. Tests are deliberately withheld at this stage — the clinician must gather more history first.

2. **Stage 2:  Investigation recommendations:** After the clinician answers the follow-up questions, the model returns a prioritised list of investigations as its primary output, with a working differential as supporting context only. The model is explicitly instructed not to state a confirmed diagnosis at this stage.

3. **Stage 3: Clinical advisory:** After the clinician enters real investigation results, the model returns a management advisory - options for consideration, not orders. The system prompt and output schema both require the model to include an advisory note explicitly stating that the treating clinician retains all decision authority.

This structure reflects actual clinical reasoning protocol and prevents the model from short-circuiting to a diagnosis before sufficient evidence is gathered. Stage ordering is enforced in both interfaces: the web UI disables later-stage buttons until earlier stages succeed, and the terminal CLI requires non-empty input at each gate.

### Model choice

The model is a GGUF-quantized language model selected for its performance on structured JSON output and medical reasoning tasks within the constraints of a CPU-only district hospital laptop. The Q4_K_M quantization was chosen as the balance point between output quality and memory footprint - fitting within 8 GB RAM while maintaining coherent, schema-valid JSON responses.

**Alternatives evaluated:**
- Q5_K_M: better quality but pushes closer to the 8 GB RAM ceiling on context sizes above 1024 tokens; rejected for margin of safety.
- Q3_K_M: fits more comfortably in RAM but shows more frequent JSON schema violations on structured output tasks; rejected.
- Q8_0: high quality but exceeds the 8 GB RAM profile for models above ~3B parameters; rejected.

### Prompt engineering

All three pipeline stages use a `### System / ### Instruction / ### Input / ### Response` format that mirrors the instruction-tuning format used by most modern fine-tuned GGUF models. Each instruction is written to:
- Specify the exact JSON output schema with field names and types
- Explicitly constrain what the model should and should not output at each stage (e.g. "do not recommend tests yet" in Stage 1; "do not state a confirmed diagnosis" in Stage 2; "do not issue a treatment order" in Stage 3)
- Require the model to produce an advisory note that names the clinician's decision authority in Stage 3

### Offline-first architecture

The system calls the llama.cpp binary as an external subprocess — `llama-completion` on current builds, falling back to `llama-cli` on older ones, since newer llama.cpp moved one-shot completion out of `llama-cli` into a separate binary. There are no Python model-loading libraries, no network calls during inference, and no external API dependencies. Once the model file and binary are on disk, the system runs with no internet connection required.

### Interfaces

Three interfaces share a single inference layer (`inference/aletheia.py`):
- **Web UI** (`aletheia/server.py` + `aletheia/ui/index.html`) - served by Python's standard library, enforces stage ordering via disabled buttons
- **Terminal CLI** (`cli.py`) - sequential, requires non-empty input at each stage gate
- **Single-stage CLI** (`run.py`) - for scripting and profiler integration; accepts `--stage` and `--extra` arguments

---

## 3. Constraints

### Hardware

Target hardware: a consumer laptop with 4 CPU cores and 8 GB RAM, integrated graphics only. No GPU acceleration is used (`-ngl 0` is passed to the llama.cpp runner). The system must remain within the 8 GB RAM profile during inference, including OS overhead.

Context size is set to 1024 tokens. At this context length, the Q4_K_M quantization keeps peak RSS well within the profiler's 7 GB scoring threshold for most models in the 3–8B parameter range.

### Connectivity

Zero internet access during inference. The download script (`download_model.sh`) fetches weights once before use. After that, the system is fully air-gapped.

### Data and training constraints

Aletheia is designed for conditions prevalent in East and Central Africa: malaria, meningitis, TB, typhoid, obstetric emergencies, snakebite, severe acute malnutrition, and others that are underrepresented in models trained primarily on Western medical literature. The system prompt explicitly anchors the model to this context ("district hospitals and health centres in sub-Saharan Africa") and instructs it to prioritise conditions prevalent in the region.

### Regulatory framing

Clinical AI in Uganda operates without a formal regulatory framework for AI-based decision support as of 2026. Aletheia is presented as a research prototype, not a licensed medical device. Every output carries explicit advisory framing. This is a design constraint as much as a legal one - the system must not produce output that a clinician could mistake for a final diagnosis or treatment order.

---

## 4. Benchmarks

All measurements produced by the ADTC profiler (`adtc-profiler 0.1.0`) running in participant mode on the participant's development machine. Raw output is in `benchmark/submission.json`.

### Runtime Performance

| Metric | Value |
|---|---|
| Machine | Intel Core i5-8350U @ 1.70 GHz |
| RAM available | 9.7 GB |
| OS | Ubuntu 26.04 LTS (WSL2) |
| Inference runtime | llama.cpp b10733 (CPU only, `-ngl 0`) |
| Quantization | GGUF Q4_K_M |
| Model file size | 1.80 GB |
| Prompt tokens (profiler run) | 512 |
| Generated tokens (profiler run) | 128 |
| Peak RSS | 3,281 MB |
| Steady-state RSS | 3,121 MB |
| Peak VMS | 3,771 MB |
| Tokens per second (generation) | **5.68 t/s** |
| First token latency (512-token prompt) | 29,986 ms (30.0 s) |
| CPU utilization (p99) | 51.0% |
| Throttled | No |

These are the values in `benchmark/submission.json` in this repository, reproducible by
running `bash benchmark/run_adtc_profiler.sh`.

An earlier profiling run on Ubuntu 22.04.5 with an older llama.cpp build recorded
3.71 t/s and 32.7 s to first token, with peak RSS of 3,273 MB. Memory was effectively
identical (within 0.25%); the throughput difference comes from the llama.cpp build. The
figures above supersede it.

First-token latency above is for a 512-token stress prompt. Typical Stage 1 prompts are 50–100 tokens and will produce substantially lower first-token latency.

### ADTC Compliance

| Metric | Value | ADTC Limit | Status |
|---|---|---|---|
| Peak RSS | 3,281 MB | 7,168 MB | **✅ PASS** (3,887 MB margin) |
| Internet required at inference | None | None | **✅ PASS** |
| GPU required | None | None | **✅ PASS** |
| African use case | Healthcare, Uganda | +10 pts bonus | **✅ YES** |

### Clinical Accuracy

Evaluated on a 3,000-sample held-out set drawn from the same 50-condition distribution as training data.

> These figures come from our own held-out evaluation, not from the ADTC profiler. The
> profiler was run with `--skip-accuracy`, so the `accuracy` array in
> `benchmark/submission.json` is intentionally empty.

| Metric | Value |
|---|---|
| Top-1 Diagnostic Accuracy | **80.0%** |
| Top-3 Diagnostic Accuracy | **100.0%** |
| ROUGE-1 F1 | 0.383 |
| ROUGE-2 F1 | 0.266 |
| ROUGE-L F1 | 0.349 |
| BERTScore F1 | **0.909** |
| METEOR | 0.467 |
| ECE (Expected Calibration Error) | 0.275 |

Top-3 accuracy of 100% means the correct diagnosis is always present in the ranked differential — critical for ensuring no life-threatening condition (meningitis, eclampsia, cerebral malaria) is missed under time pressure.

ECE of 0.275 indicates moderate calibration; probability estimates should be treated as relative rankings rather than precise confidence values.

### Training Details

| Parameter | Value |
|---|---|
| Base model | Qwen2.5-3B-Instruct |
| Fine-tuning method | QLoRA (4-bit, BFloat16) |
| LoRA rank / alpha / dropout | 32 / 64 / 0.05 |
| Target modules | q\_proj, k\_proj, v\_proj, o\_proj, gate\_proj, up\_proj, down\_proj |
| Trainable parameters | 59,867,136 (1.94% of total) |
| Training samples | 27,000 (train) · 3,000 (eval) |
| Dataset mix | 60% Aletheia-Synthetic · 20% MedQA-USMLE · 20% MedMCQA |
| Training epochs | 3 |
| Effective batch size | 16 |
| Learning rate | 2 × 10⁻⁴ (cosine with 5% warmup) |
| Final training loss | 0.5197 |
| Training hardware | NVIDIA A100-SXM4-80GB (Google Colab Pro) |
| Training time | 1.92 hours |

---

## 5. Ethical Considerations

Aletheia is a decision support tool, not an autonomous clinical actor. Several design choices reflect this:

- The pipeline cannot be short-circuited to a final output without passing through all prior stages.
- Stage 3 output uses the word "advisory" in both the section header and a required JSON field (`clinical_advisory_note`) that instructs the model to reiterate the clinician's decision authority.
- The system is framed as a "second opinion" and "structured reasoning support," not as a replacement for clinical training or specialist consultation.
- No patient data is stored, transmitted, or logged by the system.

The African Deep Tech Challenge's vision of locally-run, low-resource-appropriate AI is directly aligned with Aletheia's design: a tool that is useful precisely because it works in the places where cloud-dependent tools fail.
