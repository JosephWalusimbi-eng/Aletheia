# Aletheia: Offline-First Clinical Decision Support for Resource-Constrained Healthcare

## 1. Inspiration

At Soroti Regional Referral Hospital in Eastern Uganda, a single clinical officer may see between 80 and 120 patients in a single day. This can leave fewer than five minutes per patient to take a history, conduct an examination, establish a diagnosis, and determine an appropriate course of management. Under such intense cognitive pressure, critical clinical presentations can be missed, not because the clinician lacks competence, but because the workload is overwhelming.

Uganda also faces a severe shortage of medical personnel relative to the size of its population. At the same time, many artificial intelligence systems designed to support clinical decision-making depend on cloud servers, reliable high-speed internet connections, and expensive computing hardware. These requirements are often unavailable at the point of care in rural and resource-constrained settings.

Aletheia was developed to address this gap.

The name **Aletheia** is derived from the Greek concept of *aletheia*, meaning truth, disclosure, or the revealing of what is hidden. This reflects the fundamental purpose of diagnosis: systematically uncovering the most likely explanation for a patient's presentation.

## 2. What Aletheia Does

Aletheia is an **offline-first clinical decision support system** designed to guide clinicians through three ordered stages of clinical reasoning. The workflow is deliberately structured to mirror the way clinical assessment progresses from an initial presentation to investigation and, ultimately, clinical management.

### Stage 1: Initial Assessment

The clinician enters the patient's symptoms, their duration, and other relevant clinical information.

Aletheia then produces:

* A tentative, ranked differential diagnosis.
* Probability estimates for the suggested conditions.
* Severity ratings.
* Three to five targeted follow-up questions intended to narrow the differential diagnosis.
* Red flags requiring immediate escalation.

At this stage, diagnostic investigations are deliberately withheld. The model is explicitly instructed not to recommend investigations until the clinician has answered the targeted follow-up questions.

### Stage 2: Investigation Recommendations

After the clinician provides answers to the follow-up questions, Aletheia produces a prioritised list of investigations that are available at the district-hospital level.

The investigation recommendations are the primary output of this stage. The differential diagnosis generated in Stage 1 is retained as supporting context rather than treated as a confirmed diagnosis.

The model is explicitly instructed not to state a confirmed diagnosis before the relevant investigation results are available.

### Stage 3: Clinical Advisory

Once the clinician enters the actual investigation results, Aletheia produces a clinical management advisory.

This includes:

* The most likely diagnosis.
* Diagnostic confidence.
* Appropriate management options.
* The recommended first step in management.
* Additional investigations where uncertainty remains.

Every Stage 3 output contains an explicit advisory statement that the treating clinician retains full decision-making authority. Aletheia does not prescribe treatment or replace the clinician.

### Enforced Stage Ordering

The three-stage workflow is enforced both graphically and technically. It is not possible to proceed directly to Stage 3 without completing Stages 1 and 2.

This design prevents the system from presenting a premature diagnosis without the clinical reasoning and investigation steps that should precede it.

### A Refusal Boundary Enforced in Code, Not in the Prompt

Aletheia is advisory: it helps a clinician decide, it does not prescribe. An instruction placed in a prompt cannot enforce that boundary. A fine-tuned three-billion-parameter model asked *"what dose of gentamicin for a 3 kg neonate"* will usually answer, and a wrong number in that answer is the single most dangerous output this system could produce.

The boundary is therefore enforced in code, in `inference/safety.py`, which screens the clinician's text **before any prompt is built and before llama.cpp is launched**. Five hazard classes are refused: paediatric and weight-based dosing, controlled or sedative drug dosing, general drug dosing, direct prescription requests, and lethal-dose requests. A refusal names its class, explains why Aletheia will not answer, and directs the clinician to the national formulary or the ward dosing chart, while offering to continue with the differential, the investigations and the red flags.

Each class requires **two independent signals** to fire: a request marker, indicating that the clinician is asking for something, and a hazard marker, indicating what is being asked for. Screening on the hazard marker alone would refuse ordinary clinical history, since a Stage 2 entry such as *"gave 500 mg ceftriaxone at 0600, creatinine now 180"* is entirely legitimate and must pass straight through. The lethal-dose class is the single exception, as its phrasings are unambiguous on their own.

The distinction matters. A refusal enforced in code is deterministic, testable and reviewable. A refusal that depends on the model continuing to honour its instruction is none of those things.

### Session Recall

A single stage on the target hardware costs 40 to 60 seconds of CPU time, and district practice is repetitive: the same presentation arrives at the same clinic several times in a season. Re-deriving an answer the clinician has already seen and accepted spends the scarcest resource on the machine in order to arrive back where it started.

When a session completes, the clinician is therefore offered three options, and none of them is the default:

1. **Save** — keep the results as they stand.
2. **Edit, then save** — correct the output first, then keep the corrected version.
3. **Exit without saving** — discard everything; nothing is written.

The middle option carries most of the clinical value. What is stored after an edit is no longer a model output; it is a record that a clinician has read, corrected and signed off. A saved case is marked with which of the two it is.

When a later presentation matches a saved case, it is answered from the record rather than from the model. The match is computed over the inputs that define the situation: the normalised symptom set, the duration band, the age group, the sex, the stage being run, and that stage's own input. A stage whose inputs differ falls through to the model as normal.

Four rules govern recall, and each one prevents a specific failure:

* **A recalled result is always labelled as recalled**, together with the date it was saved and whether a clinician edited it. A cached recommendation presented as a fresh one invites a clinician to read corroboration into what is only repetition.
* **A fresh run is always available.** The clinician can reject the recalled result and run the model regardless of match quality. Recall is an offer, never a substitution.
* **The safety screen runs before recall, not after.** A paediatric dosing question is refused on a matched case exactly as it is on a cold run. Recall cannot become a route around a guardrail.
* **Saved cases age.** A case older than a configurable threshold is surfaced with its age shown, so that the clinician decides whether older reasoning still applies.

**A saved case describes a presentation, not a person.** Aletheia has no field in which a patient identity could be recorded. The input schema consists of the symptom list, the duration in days, an age *band* rather than a date of birth, and sex. There is no name, no patient number, no facility and no admission date. A saved case therefore has the same clinical shape as a textbook vignette. This is a property of the schema rather than a promise about handling: the identifiers are not protected, they are never collected in the first place, so the store has nothing to disclose even if the machine is lost.

Storage is a single plain JSON file on the local disk. It is never synced or transmitted, it is readable and deletable by the clinician who owns the machine, and the system runs normally when it is absent.

The store is `inference/recall.py`, carrying its own self-checks in the same way as the safety module. All three interfaces use it: the web console offers the three choices after each stage and shows a provenance banner on a recalled one, the terminal CLI offers them once at the end of a consultation, and `run.py` takes `--recall`, `--save`, `--list-cases` and `--forget`.

Recall is opt-in in `run.py` alone, and deliberately so: a scripted run — a benchmark above all — must measure the model, and a store that silently answered on its behalf would report throughput that no inference produced. Every benchmark figure below is a cold-run measurement and none of them depend on recall.

### Clinical Coverage

Aletheia currently covers **50 disease conditions with elevated prevalence across sub-Saharan Africa**. These include conditions such as:

* Cerebral malaria
* Bacterial meningitis
* Eclampsia
* Postpartum haemorrhage
* Severe sepsis
* Snake envenomation
* Visceral leishmaniasis
* Tuberculosis

The system is designed around conditions that are particularly relevant to the African clinical context and that are often poorly represented in conventional Western medical AI benchmarks.

## 3. Offline Deployment

Aletheia runs entirely on an **Intel Core i5-8350U laptop at 1.70 GHz**, without an internet connection, a dedicated GPU, or any cloud dependency.

Measured peak RSS is **3,281 MB**, leaving approximately **3,887 MB of headroom** beneath the 7,168 MB ADTC memory ceiling.

This makes the system suitable for environments where reliable internet connectivity and high-performance computing resources cannot be assumed.

## 4. How We Built It

### Base Model

The base model selected for Aletheia was **Qwen2.5-3B-Instruct**. It was selected because it provided an appropriate balance between model performance and parameter count, allowing the model to fit within the available memory budget after quantisation.

### Fine-Tuning

Aletheia was fine-tuned using **QLoRA** in 4-bit with BFloat16 compute, with:

* Rank (*r*) = 32
* Alpha = 64
* Dropout = 0.05
* All seven linear projection layers targeted
* 59,867,136 trainable parameters
* Approximately 1.94% of the total model parameters trained

Training was conducted on Google Colab Pro using an **NVIDIA A100-SXM4-80GB** GPU over three epochs, taking **1.92 hours**, with an effective batch size of 16 and a learning rate of 2 × 10⁻⁴ on a cosine schedule with 5% warmup. The final training loss was 0.5197.

### Dataset

The corpus contains **30,000 clinical reasoning samples**, split into **27,000 for training and 3,000 held out for evaluation**.

Its composition is:

* 18,000 Africa-weighted synthetic clinical samples covering 50 conditions (60%).
* 6,000 filtered MedQA-USMLE questions (20%).
* 6,000 filtered MedMCQA questions (20%).

This combination was designed to balance Africa-specific clinical relevance with broader medical reasoning capability.

### Deployment

The merged model was converted to **GGUF Q4_K_M format**, producing a deployment model of **1.93 GB** (1,929,902,592 bytes; 1.80 GiB, which some tools display as "1.8G").

The conversion pipeline used `llama.cpp` and followed a two-step process:

1. Conversion to F16 GGUF.
2. Quantisation using `llama-quantize`.

The resulting inference engine uses `llama.cpp` compiled for CPU-only operation and invoked as an external subprocess with `-ngl 0`. There are no Python model-loading libraries and no network calls at inference time.

The model weights are hosted on Hugging Face and are retrieved using a download process that verifies both the expected byte count and the GGUF magic bytes before reporting a successful download.

### Interfaces

Aletheia provides three interfaces that share a common inference layer, `inference/aletheia.py`.

The primary web interface is served using Python's standard library through a lightweight JSON API. The interface contains its own CSS and JavaScript, requires no build step, and does not depend on external assets.

The interface enforces the three-stage workflow through button states:

* Step 2 remains disabled until Step 1 is successfully completed.
* Step 3 remains disabled until Step 2 is successfully completed.

Because a stage takes 40 to 60 seconds on the target hardware, the interface **streams generated tokens over server-sent events** as the model produces them, rather than leaving a blank panel until the stage finishes. Elapsed time and a live tokens-per-second figure are shown alongside the stream, and the panel reports the loaded model, its size, and the thread count read from the host machine. The server binds to 127.0.0.1 by default.

Aletheia additionally includes an interactive terminal CLI, `cli.py`, which guides the clinician through all three stages using Rich-formatted output.

A single-stage CLI, `run.py`, accepts `--stage` and `--extra` arguments, allowing individual stages to be used for scripting.

The launcher script, `start_aletheia.sh`, starts the web interface, waits for it to become available, and opens it in the browser. With the `--install-shortcut` option, it can also register a desktop entry, allowing Aletheia to be launched from the applications menu without opening a terminal.

A performance tuner, `benchmark/optimize.sh`, measures generation throughput across different thread counts on the host machine and writes the fastest configuration into the runtime settings.

## 5. Challenges and How We Addressed Them

### 5.1 MedMCQA Dataset Path Bug

A file-path error during dataset construction initially excluded the 6,000 MedMCQA samples from the training run.

The problem was identified and corrected, after which the model was retrained.

The corrected training run improved:

* **Top-1 accuracy from 70% to 80%.**
* **Top-3 accuracy from 90% to 100%.**

This demonstrated the importance of validating the complete data pipeline before training.

### 5.2 GGUF Conversion Flags

During development, a newer version of `llama.cpp` removed the `--outtype q4_k_s` flag that had previously been used in the conversion process.

The problem was resolved by adopting a more robust two-step approach: first converting the model to F16 GGUF, then performing quantisation separately.

This separation made the conversion pipeline more resilient to changes in the `llama.cpp` tooling.

### 5.3 Training Loss Versus Accuracy

The second training run produced a higher terminal loss of approximately **0.52**, compared with **0.31** in the earlier run, despite achieving substantially better diagnostic accuracy.

This resulted from the increased diversity of the training data and the broader range of question styles introduced through the corrected dataset.

The experience demonstrated that training loss alone is an incomplete proxy for clinical utility. For this application, task-specific measures such as diagnostic accuracy provide more meaningful evidence of performance.

### 5.4 Changes in the Inference Runtime

The `llama.cpp` runtime changed during development. Newer versions altered the behaviour of `llama-cli`, making it primarily a conversational front end that waits for interactive input, while one-shot completion functionality was moved into a separate `llama-completion` binary.

In addition, the `--log-disable` option began suppressing generated tokens alongside the logs.

These changes silently disrupted non-interactive inference, in some cases causing the system to return empty output.

Aletheia was therefore modified to detect the available binary at runtime and fall back gracefully. This allows the same application code to operate across different `llama.cpp` versions.

### 5.5 Removing the Web Framework

The first version of the web interface was developed using a general-purpose web framework. However, this introduced approximately 60 packages into an installation intended for machines that might have metered or intermittent connectivity.

The framework also required a heavier JavaScript bundle before the interface could be displayed.

The web interface was therefore redesigned using Python's standard library and a single self-contained webpage.

As a result, the project now declares **a single Python dependency**, `rich`, which is used only by the terminal CLI. The web interface requires none at all, and the page is one self-contained file of approximately **41 KB** with no external assets.

This reduction is particularly important for offline-first software, because every dependency represents something that must be installed and maintained on a machine that may never connect to the internet again.

### 5.6 Hyperthreading and Inference Performance

Initial setup scripts configured `llama.cpp` to use one thread per logical CPU core, based on the output of `nproc`.

On the development laptop, this resulted in eight threads being used on a four-core, eight-thread processor. However, this proved to be the worst-performing configuration.

Because `llama.cpp` performs dense matrix computations, multiple threads sharing the execution resources of the same physical core can compete with rather than complement one another.

Benchmarking showed:

* **8 threads:** 4.14 tokens per second.
* **4 threads:** 7.10 tokens per second.

Thread tuning therefore increased generation throughput substantially and reduced the duration of a complete pipeline stage from approximately **79 seconds to 46 seconds**.

Rather than hard-coding four threads, the project includes a benchmarking tuner, because the optimal configuration depends on the hardware on which Aletheia is deployed.

### 5.7 Hosting Large Model Weights

The model weights were initially hosted on Google Drive. However, Google Drive does not provide convenient resume support for interrupted downloads and imposes daily per-file quotas.

During testing, a large model download stalled twice and had to be manually terminated and restarted.

For a 1.93 GB model file being downloaded over an intermittent connection, this was impractical.

The weights were therefore moved to Hugging Face, which provides access over HTTPS and supports range requests. This allows interrupted downloads to resume using commands such as `curl -C -`, rather than requiring the entire file to be downloaded again.

The resume functionality was verified by downloading approximately 500 MB, interrupting the transfer, resuming it, and confirming that the final file was byte-identical to the original.

### 5.8 CPU Inference Latency

CPU inference is inherently slower than GPU inference.

Under the ADTC profiler's benchmark settings, using a 512-token prompt and 128 generated tokens, Aletheia achieved:

* **5.68 tokens per second**
* **30.0 seconds to first token**

That first-token figure is a stress case rather than a typical one. The profiler prepends a 512-token prompt, whereas real Stage 1 prompts run to roughly 50 to 100 tokens and produce substantially faster first output.

After thread tuning, a complete three-stage consultation takes approximately **2 to 2.5 minutes end-to-end**.

Although this is slower than GPU-based inference, the response time is practical for a clinical reasoning workflow, and it compares favourably with waiting for a specialist referral.

Further improvements are expected on the intended ADTC target hardware using 10th- to 12th-generation Intel Core i5 processors.

### 5.9 A Small Model Gets the Medicine Right and the Schema Wrong

A three-billion-parameter model proved considerably more reliable at producing correct clinical content than at producing the exact key names it had been instructed to use. In testing, Stage 2 returned a complete and clinically sound working differential under the key `working_differentials`, while every consumer of that output was reading `working_differential`. The interface correctly reported that no differential had been returned, on a response that in fact contained a good one.

The failure was instructive because it was invisible from the model's side. The generation was correct; only the label was wrong, and the schema instruction in the prompt had not been sufficient to prevent the drift.

Rather than adding a synonym list to each of the four consumers — the streaming web path, the blocking web path, the terminal CLI and the scripting CLI — the correction was placed at the single point through which all four parse their output. Known key drift is now mapped back onto the documented schema on a per-stage basis, and an alias is applied only when the canonical key is genuinely absent, so a correct response is never overwritten by a synonym the model happened to emit alongside it.

The lesson generalises: with a small model, treat the output schema as something to be reconciled at the boundary, rather than as something the prompt can be relied upon to guarantee.

### 5.10 Early-Stage Multilingual Fine-Tuning

Aletheia was also initially extended toward Kiswahili through continued fine-tuning of the existing LoRA adapter.

Initial evaluation metrics, including ROUGE and BERTScore, appeared promising. However, manual inspection of held-out clinical cases revealed that the model was beginning to converge toward a small number of frequent diagnoses instead of reliably discriminating across the full set of conditions.

This highlighted an important limitation of aggregate text-similarity metrics in clinical applications.

The experience demonstrated that metrics such as ROUGE and BERTScore cannot, by themselves, establish clinical correctness. Direct case-by-case verification remains essential.

Kiswahili development is continuing, but **English remains the validated language version**.

## 6. Accomplishments

### 6.1 100% Top-3 Diagnostic Accuracy

Aletheia achieved **100% Top-3 accuracy** and **80% Top-1 accuracy** on the 3,000-sample held-out evaluation set.

In other words, the correct diagnosis appeared among Aletheia's three highest-ranked suggestions for every test case.

These are internally generated held-out results, and the evaluation set is drawn from the same 50-condition distribution as the training data. The figure should therefore be read as evidence of consistent in-distribution ranking, rather than as a measure of performance on unseen real-world presentations, which remains to be established through external clinical validation.

### 6.2 1.93 GB Deployment Size

The three-billion-parameter model was compressed to **1.93 GB** without a meaningful loss in measured performance.

The resulting model is small enough to fit on a USB drive, making physical distribution and offline deployment practical.

### 6.3 A Web Interface With Zero Third-Party Dependencies

The web interface is served using Python's standard library and consists of a single self-contained webpage of approximately **41 KB**, which loads in under 10 milliseconds and requires no external assets, no build step and no CDN.

The project declares **one Python dependency** in total, `rich`, needed only by the terminal CLI, against approximately 60 packages in the original web-framework implementation.

### 6.4 71% Increase in Throughput Through Measurement

Optimising the number of CPU threads on the basis of physical rather than logical cores increased generation throughput from **4.14 to 7.10 tokens per second** without changing the underlying model.

This represents approximately a **71% increase in throughput**, and it reduced a full pipeline stage from 79 seconds to 46.

The optimisation is included in the project as a tuner, allowing the system to identify an appropriate configuration for different deployment machines.

### 6.5 3,281 MB Peak RAM Usage

Measured peak RSS was **3,281 MB**, leaving approximately **3,887 MB below the 7,168 MB ADTC memory ceiling**, with steady-state RSS of 3,121 MB.

This provides a substantial operating margin rather than placing the system at the edge of the available memory limit.

Memory usage remained stable, varying by less than 0.25% across two operating-system versions and different `llama.cpp` builds.

### 6.6 BERTScore-F1 of 0.909

Aletheia achieved a **BERTScore-F1 of 0.909** on the evaluated clinical reasoning outputs.

This indicates a high degree of semantic similarity between the model's generated reasoning text and the expert reference answers.

However, semantic similarity should be interpreted alongside clinical correctness rather than treated as a standalone measure of clinical safety or utility. The Kiswahili work described in section 5.10 is a direct demonstration of why.

### 6.7 A Safety Boundary That Does Not Depend on the Model

The highest-harm output this system could produce, a paediatric dose, is refused in code before the model is ever invoked. Five hazard classes are covered, using a two-signal design that leaves ordinary clinical history untouched.

This is an accomplishment rather than a limitation. It means the safety property holds even if the model is swapped, retrained, or drifts, because it was never the model's property to enforce.

### 6.8 Coverage of 50 African Clinical Conditions

Aletheia currently covers **50 clinical conditions relevant to sub-Saharan Africa**, including conditions such as candidiasis, Buruli ulcer, and schistosomiasis.

Many of these conditions are poorly represented in conventional Western medical AI benchmarks, making Africa-specific clinical coverage an important component of the system's design.

## 7. What We Learned

The development of Aletheia produced several important lessons.

### 7.1 Loss Is Not the Most Important Metric for Clinical AI

The most significant lesson was that training loss is not necessarily the metric that matters most for clinical AI.

A model trained on more diverse data produced a higher terminal loss while simultaneously achieving better clinical accuracy.

For clinical decision-support systems, evaluation should therefore incorporate domain-appropriate measures such as **Top-k accuracy, BERTScore, calibration, and direct clinical case verification**, rather than relying solely on training loss.

### 7.2 Dataset Quality Matters More Than Dataset Size

Aletheia's development also demonstrated that dataset quality can be more important than dataset size.

The Africa-weighted synthetic dataset was carefully designed around relevant clinical cases and conditions. Its contribution to performance reinforced the importance of constructing high-quality, clinically meaningful training examples.

A smaller, well-designed dataset can therefore be more valuable than a larger dataset that lacks focus or contextual relevance.

### 7.3 A Prompt Is Not a Guarantee

Two separate failures taught the same lesson from opposite directions.

The model was instructed not to give doses, and would have done so anyway. The model was instructed to use a specific key name, and used a different one. In both cases the instruction was clear, and in both cases the instruction was not sufficient.

The conclusion is that anything which must be true — a safety boundary, an output contract — belongs in code that runs around the model, rather than in text that runs through it. A prompt expresses an intention. Only the surrounding system can enforce one.

### 7.4 The Deployment Pipeline Is as Important as the Model

Building a clinically useful AI system involves considerably more than training a model.

The transition from a trained model to something that a clinical officer can actually run on an offline laptop required substantial work in:

* Model quantisation.
* Runtime compilation.
* Inference integration.
* Interface development.
* Installation automation.
* Hardware optimisation.
* Dependency reduction.
* Runtime compatibility.

This deployment work proved to be nearly as important as the model-training process itself.

For offline software, reliability is particularly important because the system cannot depend on an internet connection to repair missing dependencies or retrieve updates.

Every unnecessary dependency removed from the system is one less component that can fail on a machine operating without connectivity.

### 7.5 The Obvious Default Is Worth Measuring

Another important lesson was that intuitive technical decisions are not always optimal.

Using every available logical CPU core, and hosting a large model file on the most convenient storage platform, both appeared reasonable initially.

However, measurement demonstrated that:

* Using every logical core reduced inference throughput.
* Hosting the large model file on a platform without reliable resume support created significant deployment problems.

These experiences reinforced a fundamental engineering principle: **measure the actual system rather than assuming that the obvious configuration will be the best one.**

### 7.6 The Fastest Computation Is the One You Do Not Repeat

Most of the speed work on this project involved making the model generate tokens more quickly: correcting the thread count, choosing a quantisation that fits within a realistic memory budget, and removing a framework that delayed first paint.

Session recall approaches the same problem from the opposite direction. Thread tuning took a stage from 79 seconds to 46. Recognising that a presentation has already been assessed, and that a clinician has already reviewed and corrected that assessment, takes the same stage to effectively nothing.

On hardware where generation costs 40 to 60 seconds per stage, the largest available speed-up is not computing the answer faster. It is noticing that the answer is already known. And because the clinician was offered the opportunity to correct it before it was stored, the recalled answer can be better than the one the model would generate a second time.
