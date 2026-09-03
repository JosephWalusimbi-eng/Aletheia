# Aletheia - Setup and Testing Guide

This guide walks you through getting Aletheia running from scratch on both **Windows** and **Ubuntu**, then testing each of the three interfaces end-to-end.

## Python version requirement

**Python 3.11 is required.**

There are two separate reasons for this floor:

1. **The terminal UI** uses `rich`, which supports Python 3.8 and above, so it is not the binding constraint.
2. **The ADTC profiler** (`adtc-profiler`) explicitly requires Python ≥ 3.11. You must run the profiler locally to generate benchmark numbers before submitting. If you are on 3.10, the profiler will refuse to run.

Python 3.11 satisfies both constraints. Python 3.12+ has not been tested against Aletheia's dependencies.

To check your current version:
```
python --version        # Windows
python3 --version       # Ubuntu
```

If you see `3.10.x`, upgrade to 3.11 before proceeding - the submission step will fail otherwise.

**llama.cpp has no Python requirement.** Aletheia does not use the `llama-cpp-python` bindings package. It calls the compiled `llama-cli` binary directly via `subprocess.run()` - the binary is pure C++ and runs independently of Python entirely. The Python version you install has no effect on llama.cpp's behaviour; it only affects the Aletheia Python code and the profiler.

Aletheia has two external dependencies beyond Python:
- **llama.cpp** - the inference runtime (`llama-cli` compiled C++ binary)
- **A GGUF model file** - the quantized language model (`aletheia_q4km.gguf`)

Both must be in place before any interface can run inference.

---

## Part 1: Windows Setup

Tested on Windows 10 and Windows 11.

### 1.1 Install Python

1. Download **Python 3.11** from https://www.python.org/downloads/windows/
   (On that page look for the "Python 3.11.x" Windows installer — pick the 64-bit version.)
2. Run the installer. On the first screen, **tick "Add Python to PATH"** before clicking Install.
3. Open a new Command Prompt and verify:
   ```
   python --version
   ```
   You should see `Python 3.11.x`. If you see 3.10 or lower, install 3.11 before continuing — the ADTC profiler requires it.

### 1.2 Get the Aletheia code

If you have Git installed:
```
git clone https://github.com/JosephWalusimbi-eng/Aletheia.git
cd Aletheia
```

Or download the ZIP from GitHub and extract it. All commands below assume you are inside the `Aletheia` folder.

### 1.3 Install llama.cpp (pre-built binary - recommended)

Building from source on Windows requires Visual Studio. Using a pre-built release is faster and avoids that dependency.

1. Go to https://github.com/ggerganov/llama.cpp/releases
2. Find the latest release. Download the file named something like:
   `llama-bXXXX-bin-win-cpu-x64.zip`
   (choose the `cpu` variant — Aletheia does not use a GPU)
3. Extract the ZIP. You will find a `llama-cli.exe` inside the `build\bin\` folder (exact path depends on the release).
4. Note the full path to `llama-cli.exe`. For example:
   ```
   C:\Users\YourName\Downloads\llama-b5000-bin-win-cpu-x64\build\bin\llama-cli.exe
   ```

**Alternative - build from source on Windows:**
```
# Requires CMake and Visual Studio Build Tools
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
cmake -B build -DLLAMA_NATIVE=OFF
cmake --build build --config Release
# Binary will be at: build\bin\Release\llama-cli.exe
```

### 1.4 Place the model file

Create a `models` folder inside the Aletheia project directory and copy your GGUF model file into it:

```
Aletheia\
  models\
    aletheia_q4km.gguf    ← place your model file here
```

If your model has a different filename, you will set the exact path in the config file (Step 1.5).

### 1.5 Create the configuration file

Create the file `inference\config.json` inside the Aletheia folder. Use Notepad or any text editor:

```json
{
    "llama_cli": "C:\\Users\\YourName\\Downloads\\llama-b5000-bin-win-cpu-x64\\build\\bin\\llama-cli.exe",
    "model_path": "C:\\Users\\YourName\\Desktop\\Aletheia\\models\\aletheia_q4km.gguf",
    "context_size": 1024,
    "threads": 4,
    "max_tokens": 512,
    "temperature": 0.1
}
```

**Important:** Use double backslashes (`\\`) in Windows paths inside JSON. Use the actual full absolute paths on your machine.

To find the full path to the Aletheia folder quickly, open the folder in Explorer, click the address bar, and copy the path shown there.

Set `threads` to your **physical** core count, not the logical count `nproc` reports. llama.cpp does dense matrix work that does not benefit from hyperthreading, so one thread per logical core is usually slower. On a 4 core, 8 thread i5 we measured 7.10 tokens per second at 4 threads against 4.14 at 8. `lscpu` shows `Core(s) per socket`, or run `bash benchmark/optimize.sh` to measure and set it automatically.

### 1.6 Create a Python virtual environment

Open a Command Prompt in the Aletheia folder (Shift + right-click → "Open PowerShell window here", or use `cd`):

```
python -m venv venv
venv\Scripts\activate
pip install rich
```

You should see `(venv)` at the start of your prompt after activation. You need to activate the venv every time you open a new terminal.

---

## Part 2 - Ubuntu Setup

Tested on Ubuntu 22.04 LTS and Ubuntu 24.04 LTS.

### 2.1 Install system dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git build-essential cmake
```

Verify Python:
```bash
python3 --version
```
You need **Python 3.11 exactly**. Ubuntu version notes:

| Ubuntu version | Default Python | Action needed |
|---|---|---|
| 20.04 LTS | 3.8 | Install 3.11 via deadsnakes PPA (option A) |
| 22.04 LTS | 3.10 | Install 3.11 via deadsnakes PPA (option A) |
| 24.04 LTS | 3.12 | Install 3.11 via deadsnakes PPA (option A) |
| 26.04 LTS | 3.14 | deadsnakes has no 3.11 build for 26.04 — use option B |

**Option A — deadsnakes PPA** (20.04 / 22.04 / 24.04):

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-distutils
```

**Option B — `uv`** (works on every Ubuntu version, including 26.04, and needs no `sudo`):

deadsnakes only publishes packages for releases it has built for, so on 26.04 option A
fails outright. `uv` fetches a self-contained CPython 3.11 into your home directory
instead, which sidesteps both that and the `externally-managed-environment` (PEP 668)
restriction that blocks system-wide `pip install` on recent Ubuntu.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"      # add to ~/.bashrc to make it permanent
uv python install 3.11
uv venv --python 3.11 venv
uv pip install -r requirements.txt        # with venv/ as the active target
uv pip install pip                        # see note below
```

This produces the same `venv/` that step 2.6 describes; activate it the same way.

> Unlike `python3.11 -m venv`, `uv venv` does **not** put `pip` inside the environment.
> Aletheia itself does not need it, but `benchmark/run_adtc_profiler.sh` calls `pip3` to
> install the ADTC profiler, so install `pip` into the venv as shown or that script will
> fall through to the system `pip3` and fail with `externally-managed-environment`.

### 2.2 Get the Aletheia code

```bash
git clone https://github.com/JosephWalusimbi-eng/Aletheia.git
cd Aletheia
```

### 2.3 Build llama.cpp

```bash
git clone https://github.com/ggerganov/llama.cpp ~/llama.cpp
cd ~/llama.cpp
cmake -B build -DLLAMA_NATIVE=OFF
cmake --build build --config Release -j$(nproc)
```

This produces the binary at `~/llama.cpp/build/bin/llama-cli`.

**Alternative — prebuilt binaries (no `cmake`, no `sudo`, no compile wait).** Upstream
publishes a CPU build for Ubuntu x86-64 with every release, which is the quickest way
onto a fresh machine:

```bash
mkdir -p ~/llama.cpp/build/bin
curl -sSL "$(curl -sSL 'https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=1' \
    | grep -o 'https[^"]*-bin-ubuntu-x64\.tar\.gz')" -o /tmp/llama.tgz
tar -xzf /tmp/llama.tgz -C /tmp
cp -a /tmp/llama-b*/* ~/llama.cpp/build/bin/
```

Verify it works:
```bash
~/llama.cpp/build/bin/llama-cli --version
```

> **Note on `llama-cli` vs `llama-completion`.** Newer llama.cpp builds turned
> `llama-cli` into a conversation-only front end: given `-p` it waits for interactive
> turns instead of completing the prompt and exiting, so it will appear to hang and peg
> every core. Those builds ship the one-shot completer as a separate `llama-completion`
> binary. Aletheia detects this automatically — `inference/aletheia.py` prefers
> `llama-completion` when it is present alongside the configured `llama_cli` and falls
> back to `llama-cli` on older builds — so you can leave `llama_cli` pointing at
> `llama-cli` in `config.json` either way.
>
> For the same reason Aletheia does **not** pass `--log-disable`: on current builds that
> flag suppresses the generated tokens along with the logs, leaving stdout empty. The
> logs go to stderr, which is captured separately, so stdout stays clean without it.

### 2.4 Place the model file

```bash
mkdir -p ~/Aletheia/model
cp /path/to/your/aletheia_q4km.gguf ~/Aletheia/model/
```

If you need to download a model from Hugging Face:
```bash
pip install huggingface-hub
huggingface-cli download <repo-id> <filename> --local-dir ~/Aletheia/model/
```

### 2.5 Create the configuration file

```bash
cat > ~/Aletheia/inference/config.json << 'EOF'
{
    "llama_cli": "/home/YOUR_USERNAME/llama.cpp/build/bin/llama-cli",
    "model_path": "/home/YOUR_USERNAME/Aletheia/model/aletheia_q4km.gguf",
    "context_size": 1024,
    "threads": 4,
    "max_tokens": 512,
    "temperature": 0.1
}
EOF
```

Replace `YOUR_USERNAME` with your actual username. You can find it with `echo $USER`.

Set `threads` to your **physical** core count, not the logical count `nproc` reports. llama.cpp does dense matrix work that does not benefit from hyperthreading, so one thread per logical core is usually slower. On a 4 core, 8 thread i5 we measured 7.10 tokens per second at 4 threads against 4.14 at 8. `lscpu` shows `Core(s) per socket`, or run `bash benchmark/optimize.sh` to measure and set it automatically.

### 2.6 Create a Python virtual environment

```bash
cd ~/Aletheia
python3.11 -m venv venv
source venv/bin/activate
pip install rich
```

> If your system default `python3` is not 3.11, use `python3.11` explicitly as shown above. You can confirm the venv is using 3.11 with `python --version` after activation.

You need to run `source venv/bin/activate` each time you open a new terminal.

---

## Part 3 — Verify the Setup (Both Platforms)

Before running any interface, confirm the core layer works.

**Windows** (with venv active, inside the Aletheia folder):
```
python -c "from inference.aletheia import build_prompt, load_config; cfg = load_config(); print('Config OK:', cfg['llama_cli']); p = build_prompt(['fever'], 2); print('Prompt built OK, length:', len(p))"
```

**Ubuntu** (with venv active):
```bash
python -c "from inference.aletheia import build_prompt, load_config; cfg = load_config(); print('Config OK:', cfg['llama_cli']); p = build_prompt(['fever'], 2); print('Prompt built OK, length:', len(p))"
```

Expected output:
```
Config OK: /path/to/llama-cli
Prompt built OK, length: 650
```

If you see `Config OK` and a non-zero length, the configuration and import layer are working correctly.

---

## Part 4: Testing the Single-Stage CLI (`run.py`)

This is the fastest way to verify that inference itself works end-to-end.

### Stage 1 - Initial assessment and follow-up questions

**Windows:**
```
python run.py --symptoms "fever, headache, neck stiffness" --duration 2 --age adult --sex unknown
```

**Ubuntu:**
```bash
python run.py --symptoms "fever, headache, neck stiffness" --duration 2 --age adult --sex unknown
```

Expected output: The inference timer runs (this may take 30 seconds to several minutes depending on your CPU), then you see:

```
FOLLOW-UP QUESTIONS:
  1. Is there neck stiffness (Kernig or Brudzinski sign)?
  2. ...

TENTATIVE DIFFERENTIAL (context only — not yet actionable):
  1. Bacterial meningitis    65%  [Critical]
  ...
```

If you see follow-up questions printed before any differential, Stage 1 is working correctly.

### Stage 2 - Investigation recommendations

Take your answers to the follow-up questions from Stage 1 and pass them via `--extra`:

**Windows:**
```
python run.py --symptoms "fever, headache, neck stiffness" --duration 2 --stage test_recommendation --extra "Kernig sign positive, no rash, vaccinated against meningitis 3 years ago, no recent travel"
```

**Ubuntu:**
```bash
python run.py --symptoms "fever, headache, neck stiffness" --duration 2 \
  --stage test_recommendation \
  --extra "Kernig sign positive, no rash, vaccinated against meningitis 3 years ago, no recent travel"
```

Expected output:
```
RECOMMENDED INVESTIGATIONS (perform these before Stage 3):
  1. Lumbar puncture with CSF analysis (urgent)
  2. Malaria rapid diagnostic test
  3. Full blood count
  ...

WORKING DIFFERENTIAL (context for test selection):
  1. Bacterial meningitis   70%
  ...
```

Investigations must appear as the primary output, before the working differential.

### Stage 3: Clinical advisory

Take your actual investigation results and pass them via `--extra`:

**Windows:**
```
python run.py --symptoms "fever, headache, neck stiffness" --duration 2 --stage advisory_conclusion --extra "CSF cloudy, WBC 2000 cells/uL 90% neutrophils, protein elevated, glucose low. Malaria RDT negative. Blood culture pending."
```

**Ubuntu:**
```bash
python run.py --symptoms "fever, headache, neck stiffness" --duration 2 \
  --stage advisory_conclusion \
  --extra "CSF cloudy, WBC 2000 cells/uL 90% neutrophils, protein elevated, glucose low. Malaria RDT negative. Blood culture pending."
```

Expected output:
```
ADVISORY -- LIKELY DIAGNOSIS: Bacterial meningitis (confidence: High)
(Decision authority: treating clinician)

MANAGEMENT OPTIONS FOR CLINICIAN'S CONSIDERATION:
  1. IV ceftriaxone 2g 12-hourly for 10-14 days
  ...

CLINICAL NOTE: All management decisions rest with the treating clinician...
```

The word "ADVISORY" must appear prominently, and the output must not be framed as a treatment order.

### Confirm that missing `--extra` is rejected

```
python run.py --symptoms "fever" --stage test_recommendation
```

Expected: an error message saying `--extra` is required. Inference must not run.

```
python run.py --symptoms "fever" --stage advisory_conclusion
```

Expected: same error. This prevents the system from skipping stages.

---

## Part 5 — Testing the Interactive Terminal (`cli.py`)

The CLI walks you through all three stages in a single session.

**Windows:**
```
python cli.py
```

**Ubuntu:**
```bash
python cli.py
```

Walk through this sequence to test the full pipeline:

**At "Symptom 1":** type `fever` and press Enter  
**At "Symptom 2":** type `headache` and press Enter  
**At "Symptom 3":** type `neck stiffness` and press Enter  
**At "Symptom 4":** press Enter (blank line ends symptom entry)  
**At "Duration (days)":** type `2` and press Enter  
**At "Select" (age group):** type `5` (Adult) and press Enter  
**At "Sex":** press Enter (defaults to unknown)  

Stage 1 runs. You should see follow-up questions printed first, then a tentative differential below them.

**At "Your answers":** type your answers, e.g.:
```
Kernig sign positive, no rash, no recent travel, vaccinated
```
Press Enter.

Stage 2 runs. You should see recommended investigations as the headline output.

You will then see the clinician action prompt:
```
ACTION REQUIRED: Perform the investigations listed above...
```

**At "Investigation results":** type fabricated results for testing, e.g.:
```
CSF cloudy, WBC 2000 neutrophilic, protein high, glucose low, malaria RDT negative
```
Press Enter.

Stage 3 runs. Verify:
- The output opens with "ADVISORY ONLY" panel
- "Management Options for Clinician's Consideration" appears (not "Treatment Plan" or "Prescription")
- A closing line states the clinician retains authority

**Test the enforcement - skipping test results:**  
Run `cli.py` again. At the "Investigation results" prompt, press Enter without typing anything.

Expected: the CLI prints a message explaining that results are required and ends the case. It must not proceed to generate an advisory without results.

---

## Part 6 - Testing the Web UI (`aletheia/server.py`)

**Windows** (from inside the Aletheia folder, with venv active):
```
python aletheia\server.py
```

**Ubuntu:**
```bash
python aletheia/server.py
```

The terminal will print `Open your browser at: http://localhost:7860`. A browser tab should open automatically.

### UI walkthrough

**Step 1 - Load an example case:**  
Scroll to "Example Cases" at the bottom and click:  
`fever, headache, neck stiffness, vomiting | 2 days | adult | unknown`

This fills the symptoms fields. Scroll back to the top.

**Step 2 - Confirm Step 2 and Step 3 buttons are greyed out (disabled).**  
The labels should appear faded and clicking them should do nothing.

**Step 3 - Click "Run Step 1: Assess Symptoms".**  
After inference completes:
- The left column shows follow-up questions with "Answer these questions before Step 2" instruction
- The right column shows the tentative differential labelled "context only — not yet actionable"
- The Step 2 button becomes clickable (no longer greyed out)
- The Step 3 button remains greyed out

**Step 4 - Enter follow-up answers:**  
In the "Answers to Follow-up Questions" text box type:
```
Kernig sign positive, no rash, vaccinated against meningitis, no recent travel, no TB contacts
```

**Step 5 - Click "Run Step 2: Get Investigation Recommendations".**  
After inference completes:
- The left column shows recommended investigations with "Perform these before Step 3" instruction
- The right column shows the working differential labelled "context for test selection — not a confirmed diagnosis"
- The Step 3 button becomes clickable

**Step 6 - Enter investigation results:**  
In the "Investigation Results" box type:
```
CSF cloudy, WBC 2000 cells/uL 90% neutrophils, protein elevated, glucose low. Malaria RDT negative. Blood culture pending.
```

**Step 7 - Click "Run Step 3: Get Clinical Advisory".**  
After inference completes:
- Output opens with "CLINICAL ADVISORY — Decision Authority: Treating Clinician" blockquote
- A "Likely Diagnosis" section appears
- Options are under "Management Options for Clinician's Consideration" — not a treatment order
- Output closes with "The treating clinician retains full authority over all management decisions."

**Step 8 - Test enforcement by re-running Step 1:**  
Click "Run Step 1" again (with any symptoms). Verify that the Step 3 button becomes disabled again immediately after Step 1 fires. This confirms that re-running an early stage resets the later stages.

---

## Part 7 - Troubleshooting

### "llama-cli not found"

The path in `inference/config.json` is wrong. Verify the path actually exists:

**Windows:** `dir "C:\path\to\llama-cli.exe"` — should list the file  
**Ubuntu:** `ls ~/llama.cpp/build/bin/llama-cli` — should list the file

### "Model not found"

The model path in `config.json` is wrong. Verify:

**Windows:** `dir "C:\path\to\aletheia_q4km.gguf"`  
**Ubuntu:** `ls ~/Aletheia/model/aletheia_q4km.gguf`

### Inference times out or is very slow

- Lower `max_tokens` in `config.json` (try `256`) for faster responses during testing
- Set `threads` to your **physical** core count, not the logical count. Run `bash benchmark/optimize.sh` to measure the fastest value on your machine.
- First inference is always slower because the model loads from disk; subsequent calls are faster

### "Address already in use"

Another process is using port 7860. Either stop it, or pick a different port:
```bash
ALETHEIA_PORT=7861 python3 aletheia/server.py
```

### "ModuleNotFoundError: No module named 'rich'"

The virtual environment is not activated. Run:

**Windows:** `venv\Scripts\activate`  
**Ubuntu:** `source venv/bin/activate`

Then retry.

### CLI output shows garbled box-drawing characters on Windows

This is a font/encoding issue in older Windows terminals. Either:
- Use Windows Terminal (download from the Microsoft Store) instead of the classic Command Prompt
- Or run with the `PYTHONIOENCODING=utf-8` prefix:
  ```
  set PYTHONIOENCODING=utf-8 && python cli.py
  ```

### Stage 2 or Stage 3 button stays greyed out after Step 1

This means Stage 1 returned an error (the inference call failed). Check the text output in the follow-up questions panel - it will show the error message. The most common cause is an incorrect path in `config.json`.
