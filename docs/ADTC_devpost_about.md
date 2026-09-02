## Inspiration

At Soroti Regional Referral Hospital in Eastern Uganda, a single clinical 
officer may see 80 to 120 patients in a single day. That is fewer than five 
minutes per patient to take a history, examine, diagnose, and decide on 
management. Under that kind of cognitive load, critical presentations get 
missed, not because the clinician is incompetent, but because they are 
overwhelmed.

Uganda has a physician-to-patient ratio of approximately 1:25,000. The tools 
that exist to support clinical decision-making require cloud servers, fast 
internet, and expensive hardware. None of these are reliably available at 
the point of care in rural Africa. The clinicians who need AI assistance the 
most are the ones with the least access to it.

Aletheia was built to close that gap. The name comes from the ancient Greek 
ἀλήθεια - meaning truth or disclosure. The revealing of what is hidden. 
That is exactly what diagnosis is.

## What it does

Aletheia is an offline-first clinical decision support system that guides 
a clinician through three ordered stages of reasoning — mirroring the 
actual clinical thought process rather than jumping straight to a diagnosis.

**Stage 1 — Initial assessment**
The clinician enters the patient's symptoms, duration, age group, and sex. 
Aletheia returns a tentative ranked differential with probability estimates 
and severity ratings, 3–5 targeted follow-up questions to narrow the 
differential, and red flags that require immediate escalation. Diagnostic 
tests are deliberately withheld at this stage — the model is explicitly 
instructed not to recommend investigations until the clinician has answered 
the follow-up questions.

**Stage 2 — Investigation recommendations**
After the clinician provides answers to the follow-up questions, Aletheia 
returns a prioritised list of investigations available at district hospital 
level. This is the primary output at this stage. A working differential is 
included as supporting context only — the model is instructed not to state 
a confirmed diagnosis before test results are in hand.

**Stage 3 — Clinical advisory**
After the clinician enters the real investigation results, Aletheia returns 
a management advisory: the most likely diagnosis, diagnostic confidence, 
management options for the clinician to consider, a suggested first step, 
and further investigations if uncertainty remains. Every Stage 3 output 
includes an explicit advisory note stating that the treating clinician 
retains full decision authority. Aletheia does not prescribe. It advises.

Stage ordering is enforced in both graphical and terminal interfaces — 
it is not possible to skip to Stage 3 without completing Stages 1 and 2.

The system covers 50 disease conditions with elevated prevalence across 
sub-Saharan Africa, including cerebral malaria, bacterial meningitis, 
eclampsia, postpartum haemorrhage, severe acute malnutrition, neonatal 
sepsis, snake envenomation, visceral leishmaniasis, and tuberculosis.

It runs entirely on an Intel Core i5 laptop with no internet connection, no 
GPU, and no cloud dependency. Measured peak RAM usage is 3,281 MB, leaving 
3,887 MB of headroom beneath the 7,168 MB ADTC memory ceiling.

## How we built it

**Base model:** Qwen2.5-3B-Instruct was selected for its strong 
instruction-following performance at a parameter count that fits within the 
ADTC memory budget after quantisation.

**Fine-tuning:** We applied QLoRA (r=32, α=64) across all 7 linear 
projection layers, training 59,867,136 parameters (1.94% of total). 
Training ran on Google Colab Pro (NVIDIA A100-SXM4-80GB) for 1.92 hours 
across 3 epochs.

**Dataset:** 30,000 clinical reasoning samples across 3 sources, split 
27,000 train / 3,000 held-out eval:
- 18,000 Africa-weighted synthetic samples (50 conditions, 8 reasoning types)
- 6,000 MedQA-USMLE filtered questions
- 6,000 MedMCQA filtered questions

**Deployment:** The merged model was converted to GGUF format and quantised 
to Q4_K_M (1.80 GB) using llama.cpp's two-step pipeline: F16 conversion 
followed by llama-quantize. The inference engine is llama.cpp compiled for 
CPU-only operation.

**Interface:** Three interfaces share a single inference layer. A 
web UI running on localhost enforces stage ordering through 
button state — the Stage 2 button is disabled until Stage 1 succeeds, and 
Stage 3 is disabled until Stage 2 succeeds, making it impossible to skip 
steps. An interactive terminal CLI (`cli.py`) walks the clinician through 
all three stages sequentially using Rich-formatted output. A single-stage 
CLI (`run.py`) accepts `--stage` and `--extra` arguments for scripting and 
profiler integration. A launcher script (`start_aletheia.sh`) starts the 
web UI, waits for it to come up, and opens the browser; with 
`--install-shortcut` it registers a desktop entry so Aletheia opens from 
the applications menu without a terminal.

## Challenges we ran into

**MedMCQA path bug:** A file path error during dataset construction 
excluded 6,000 MedMCQA samples from the first training run. We identified 
this, corrected the pipeline, and retrained on the full 27,000-sample 
dataset. The corrected run improved Top-1 accuracy from 70% to 80% and 
Top-3 accuracy from 90% to 100%.

**GGUF conversion flags:** The newer llama.cpp removed the `--outtype 
q4_k_s` flag. We solved this by switching to a two-step process: convert 
to F16 GGUF first, then use `llama-quantize` for compression - a more 
robust approach that separates conversion from quantisation.

**Training loss vs accuracy tradeoff:** The second training run showed 
higher terminal loss (0.52 vs 0.31) despite better accuracy. This reflects 
the increased task diversity from MedMCQA, which exposes the model to 
broader question styles. Loss alone is an incomplete proxy for clinical 
utility - accuracy is what matters.

**CPU inference latency:** llama.cpp on CPU is slower than GPU inference. 
On our development machine (Intel Core i5-8350U — older than the ADTC 
target), a 512-token stress prompt produces a first token in 30.0 seconds, 
after which generation proceeds at 5.68 tokens per second. On the ADTC 
target hardware (i5 10th–12th gen) we expect further improvement. Typical 
Stage 1 prompts are 50–100 tokens, well under the 512-token stress case, 
and a full three-stage consultation takes roughly 2–3 minutes end-to-end — 
acceptable where structured reasoning time is normal, and substantially 
faster than waiting for a specialist referral.

**Early-stage multilingual fine-tuning:** We began extending Aletheia to 
Kiswahili through continued fine-tuning from the existing LoRA adapter. 
Initial evaluation metrics (ROUGE, BERTScore, JSON validity) looked strong, 
but manual spot-checks against held-out clinical cases revealed the model 
was converging toward a small number of frequent diagnoses rather than 
discriminating correctly across the full condition set. This is a known 
failure mode in early-stage low-resource fine-tuning, and it taught us that 
aggregate text-similarity metrics are not sufficient evidence of clinical 
correctness — only direct case-by-case verification is. We are continuing 
this work, but English is the validated language for this submission.

## Accomplishments that we're proud of

**100% Top-3 accuracy** on our 3,000-sample held-out evaluation set - the 
correct diagnosis appears in Aletheia's top 3 suggestions for every test 
case. In clinical practice, this means a clinician reviewing three ranked 
options will almost never miss the correct diagnosis. (These are our own 
held-out figures; the ADTC profiler was run with `--skip-accuracy`.)

**1.80 GB deployment** - a 3-billion parameter clinical reasoning model 
compressed to under 2 GB without meaningful quality loss. It fits on a 
USB drive.

**3,281 MB measured peak RAM** - 3,887 MB below the ADTC ceiling. This is 
not a tight squeeze — it is a comfortable margin that leaves room for the 
operating system, other applications, and future model improvements.

**BERTScore-F1 of 0.909** - the model's clinical reasoning text is 
semantically very close to expert reference answers. It is not just naming 
the right diagnosis; it is explaining the right reasoning.

**50 African clinical conditions** including conditions like visceral 
leishmaniasis, Buruli ulcer, and schistosomiasis that are almost never 
represented in Western medical AI benchmarks

## What we learned

The biggest lesson was that **loss is not the metric that matters for 
clinical AI.** A model trained on more diverse data had higher loss but 
better clinical accuracy. Evaluating AI in healthcare requires 
domain-appropriate metrics - Top-k accuracy, BERTScore, and calibration - not just training loss.

We also learned that **dataset quality matters more than dataset size.** 
The Africa-weighted synthetic dataset with careful clinical case design 
contributed more to performance than raw MCQ volume. A small, well-designed 
dataset beats a large, unfocused one.

We learned that **the deployment pipeline is as important as the 
model.** Getting from a trained model to something a clinical officer can 
actually run on an offline Ubuntu laptop required as much engineering 
effort as the training itself - quantisation, compilation, inference 
wrapping, and installation scripting.

Finally, our early Kiswahili experiments taught us that **automated 
evaluation metrics can be quietly misleading in low-resource language 
settings.** A model can score well on ROUGE and BERTScore while still 
defaulting to a narrow set of confident-sounding but incorrect diagnoses. 
For clinical AI, manual case-by-case verification against domain experts 
is not optional, it is the actual test that matters.

## What's next for Aletheia: Offline Clinical Reasoning Engine

**Prospective clinical validation** - we are planning a validation study 
across multiple health facilities in Eastern Uganda involving 50+ clinical 
officers and 500+ patient cases, subject to IRB approval from Soroti 
University and the Uganda National Council for Science and Technology.

**Expanded condition coverage** - growing from 50 to 100+ clinical 
conditions, with deeper coverage of obstetric emergencies, paediatric 
dosing, trauma triage, and mental health.

**Language support** - Kiswahili and Ateso interfaces are in active 
development. We have identified a mode-collapse issue in our first 
Kiswahili fine-tuning attempt and are working with our clinical co-authors 
to rebuild the training data with greater per-condition lexical diversity 
before the next training run. English remains the validated submission 
language for ADTC 2026.

**Packaged desktop application** - a launcher and desktop entry now ship 
with Aletheia, so a clinician opens it from the applications menu rather 
than a command line. What remains is a packaged installer that bundles the 
Python runtime, llama.cpp binary, and model weights, so that first-time 
setup needs no terminal either.

**Regulatory pathway** - submission to the Uganda National Drug Authority 
(NDA) under the software-as-a-medical-device framework.

**Commercialisation** - through Arapai Technologies International Limited, 
making Aletheia available to district hospitals and health centres across 
Uganda and the wider East African region.
