# Aletheia — VM Setup, Testing & ADTC Profiler Guide

Complete step-by-step instructions from creating the VM to running
the official ADTC profiler and getting your submission score.

---

## PART 1 — CREATE THE VM

### VirtualBox (free, recommended)

Download VirtualBox from https://www.virtualbox.org

**Create a new VM with these exact settings:**

| Setting | Value | Why |
|---------|-------|-----|
| Name | Aletheia-ADTC | Any name |
| Type | Linux | — |
| Version | Ubuntu 22.04 LTS (64-bit) | ADTC standard OS |
| RAM | **8192 MB (8 GB)** | Matches ADTC spec exactly |
| CPU cores | **4** | Simulates i5 10th gen |
| Storage | **60 GB** (VDI, dynamically allocated) | Model = 1.8 GB + OS |
| 3D Acceleration | **OFF** | No GPU — ADTC spec |
| Network | NAT | Internet for setup only |

**Step by step in VirtualBox:**
1. Click **New**
2. Name: `Aletheia-ADTC` → Type: Linux → Version: Ubuntu (64-bit) → Next
3. Memory: drag to **8192 MB** → Next
4. Create a virtual hard disk → VDI → Dynamically allocated → **60 GB** → Create
5. Right-click the VM → **Settings**
6. System → Processor → set to **4 CPUs**
7. Display → Screen → uncheck **Enable 3D Acceleration**
8. Click OK

> ⚠️ **Store the VM on C: drive** (e.g. `C:\VMs\VMAletheia`), not on an
> external or secondary drive (D:, E:). Storing on external drives causes
> "Failed to save the settings" errors when adding shared folders.
> If you already created the VM on another drive, move the entire VM
> folder to C: and re-add it via Machine → Add.

**Download Ubuntu 22.04 LTS:**
```
https://releases.ubuntu.com/22.04/ubuntu-22.04.5-desktop-amd64.iso
```

**Boot from ISO:**
1. Settings → Storage → click the empty CD icon
2. Click the disk icon on the right → Choose disk file → select the ISO
3. Start the VM
4. Choose **Install Ubuntu** → Minimal installation → Erase disk and install
5. Set username: `aletheia` / password: `aletheia` (or whatever you prefer)
6. Wait ~15 minutes for installation to complete
7. Restart when prompted → remove ISO when asked

---

### VMware Workstation (alternative)

| Setting | Value |
|---------|-------|
| Guest OS | Ubuntu 64-bit |
| Memory | 8 GB |
| Processors | 4 |
| Hard disk | 60 GB |
| 3D graphics | OFF |

---

## PART 2 — INITIAL UBUNTU SETUP

After Ubuntu boots for the first time:

### Step 1 — Update the system

Open a terminal (Ctrl+Alt+T) and run:

```bash
sudo apt update && sudo apt upgrade -y
```

### Step 2 — Install Python 3.11

Ubuntu 22.04 ships with Python 3.10 but the ADTC profiler requires 3.11.
The packages `python3.11-pip` and `python3.11-venv` are **not available**
directly on Ubuntu 22.04 — use the deadsnakes PPA instead:

```bash
# Add deadsnakes PPA
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update

# Install Python 3.11 and venv
sudo apt install python3.11 python3.11-venv -y

# Install pip for 3.11 separately (python3.11-pip does not exist)
curl -sS https://bootstrap.pypa.io/get-pip.py | sudo python3.11

# Set Python 3.11 as default
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo update-alternatives --set python3 /usr/bin/python3.11

# Verify
python3 --version
# Should show: Python 3.11.x

pip3 --version
# Should show pip associated with python3.11
```

> ⚠️ Do NOT try `sudo apt install python3.11-pip` — this package does not
> exist on Ubuntu 22.04 and will give an error. Use the curl method above.

### Step 3 — Install Git

```bash
sudo apt install git -y
git --version
```

---

## PART 3 — INSTALL ALETHEIA

### Step 1 — Clone the repository

```bash
cd ~
git clone https://github.com/JosephWalusimbi-eng/Aletheia.git
cd Aletheia
```

### Step 2 — Run the install script

```bash
bash install.sh
```

This will automatically:
- Install build tools (cmake, gcc, build-essential)
- Install Python packages (gradio, rich, requests)
- Clone llama.cpp from GitHub
- Build llama.cpp for CPU-only inference (takes ~5 minutes)
- Write the inference configuration file

**Expected output:**
```
[ 1/5 ] Installing system dependencies... ✅
[ 2/5 ] Installing Python packages...    ✅
[ 3/5 ] Building llama.cpp (~3 min)...  ✅
[ 4/5 ] Writing configuration...         ✅
[ 5/5 ] Checking model...
    ⚠️  Model file not found.
    Run: bash models/download_model.sh
```

The model warning is expected — you haven't downloaded it yet.

### Step 3 — Get the code from GitHub

```bash
cd ~
git clone https://github.com/JosephWalusimbi-eng/Aletheia.git
cd Aletheia
```

This gets all scripts, configs, and the full repo structure instantly.

---

### Step 4 — Download the model file from Google Drive

The model file (`aletheia_q4km.gguf`, 1.80 GB) is too large for GitHub.
Download it directly from Google Drive inside the VM.

**Get the file ID:**
1. Open Google Drive in the VM browser
2. Go to `arapai_output/gguf/`
3. Right-click `aletheia_q4km.gguf` → **Share** → **Copy link**
4. The link looks like:
   `https://drive.google.com/file/d/1XZpNCU03C65kGFqJgUMpAWNhJ-Jt2rFO/view?usp=sharing`
5. The file ID is the part between `/d/` and `/view`

**Download using gdown:**
```bash
# Install gdown
pip3 install gdown

# Download (this is the actual Aletheia model file ID)
gdown "1XZpNCU03C65kGFqJgUMpAWNhJ-Jt2rFO" \
    -O ~/Aletheia/models/aletheia_q4km.gguf
```

If gdown gives a "permission denied" or "quota exceeded" error:
```bash
# Use the fuzzy URL method instead
gdown --fuzzy \
    "https://drive.google.com/file/d/1XZpNCU03C65kGFqJgUMpAWNhJ-Jt2rFO/view?usp=sharing" \
    -O ~/Aletheia/models/aletheia_q4km.gguf
```

**Verify the download:**
```bash
ls -lh ~/Aletheia/models/aletheia_q4km.gguf
# Should show: ~1.8 GB
```

---

### Step 5 — Run the install script

Now that the repo and model are in place:

```bash
cd ~/Aletheia
bash install.sh
```

> ⚠️ Note on VirtualBox Shared Folders: if you try to set up a shared
> folder and get "Failed to save the settings" error, it is likely a
> permissions issue with the drive where the VM is stored. Use the
> gdown method above instead — it is simpler and more reliable.

**Expected output:**
```
[ 1/5 ] Installing system dependencies... ✅
[ 2/5 ] Installing Python packages...    ✅
[ 3/5 ] Building llama.cpp (~3–5 min)... ✅
[ 4/5 ] Writing configuration...         ✅
[ 5/5 ] Checking model... aletheia_q4km.gguf (1.8G) ✅
```

---

### Troubleshooting install.sh — "No module named apt_pkg"

If `bash install.sh` shows this error:

```
ModuleNotFoundError: No module named 'apt_pkg'
E: Problem executing scripts APT::Update::Post-Invoke-Success
```

This is a known Ubuntu 22.04 issue when Python 3.11 is set as default
but `python3-apt` was built for Python 3.10. Fix it first, then re-run:

```bash
# Fix apt_pkg
sudo apt install python3-apt -y

# Re-run install
bash install.sh
```

If the error persists, bypass install.sh and set up manually:

```bash
# Step A — System dependencies
sudo apt-get install -y build-essential cmake git libgomp1

# Step B — Python packages
pip3 install rich typer requests gradio

# Step C — Clone and build llama.cpp
git clone https://github.com/ggerganov/llama.cpp ~/llama.cpp --depth=1
cmake -B ~/llama.cpp/build ~/llama.cpp \
    -DCMAKE_BUILD_TYPE=Release \
    -DGGML_CUDA=OFF \
    -Wno-dev
cmake --build ~/llama.cpp/build --config Release -j$(nproc)
echo "llama.cpp built ✅"

# Step D — Write config file
# Replace 'joe' with your actual Ubuntu username (run: whoami)
USERNAME=$(whoami)
cat > ~/Aletheia/inference/config.json << EOF
{
  "llama_cli": "/home/${USERNAME}/llama.cpp/build/bin/llama-cli",
  "model_path": "/home/${USERNAME}/Aletheia/models/aletheia_q4km.gguf",
  "context_size": 1024,
  "threads": $(nproc),
  "max_tokens": 512,
  "temperature": 0.1
}
EOF
echo "Config written ✅"
echo "Manual setup complete ✅"
```

Verify the config was written correctly:
```bash
cat ~/Aletheia/inference/config.json
```

---

## PART 4 — TEST FUNCTIONALITY

Run each test in order. Each one confirms a different layer of the system.

### Test 1 — Single query (CLI)

This is the fastest test — confirms the model loads and runs:

```bash
cd ~/Aletheia

python3 run.py \
    --symptoms "fever, headache, neck stiffness" \
    --duration 2 \
    --age adult
```

**Expected output (takes 2–5 minutes on first run, faster after):**
```
Aletheia Diagnostic AI
────────────────────────────────────────
Symptoms : fever, headache, neck stiffness
Duration : 2 day(s)
Patient  : adult, unknown
Task     : initial_differential
────────────────────────────────────────
Running inference...

[142.3s]

RANKED DIFFERENTIAL DIAGNOSIS:
  1. Bacterial Meningitis          55%  ██████████████       [Critical]
  2. Viral Meningitis              20%  ████                 [High]
  3. Cerebral Malaria              15%  ███                  [Critical]
  4. Severe Typhoid                 5%  █                    [High]

PRIORITY INVESTIGATIONS:
  1. Lumbar puncture + CSF analysis
  2. Blood cultures x2 (before antibiotics)
  3. Malaria RDT STAT
  ...
```

✅ **Pass if:** You see ranked differentials in the output
❌ **Fail if:** You see "Model not found" or "llama-cli not found" — check Steps 2 and 3

---

### Test 2 — Interactive chatbot (CLI)

```bash
python3 chat/cli.py
```

At the prompt:
- Enter symptoms: `fever` → Enter, `chills` → Enter, `sweating` → Enter, then blank line
- Duration: `3`
- Age group: `5` (adult)
- Sex: `unknown`
- Task: `1` (differential diagnosis)

✅ **Pass if:** You see a formatted table of diagnoses
❌ **Fail if:** Import errors — run `pip3 install rich` and try again

Type `n` when asked "Assess another patient?" to exit.

---

### Test 3 — Web UI (Gradio)

```bash
python3 app.py
```

**Expected output:**
```
Aletheia — Starting web interface...
Open your browser at: http://localhost:7860
```

Open Firefox inside the VM and go to **http://localhost:7860**

You should see the Aletheia web interface with:
- Symptoms text box
- Duration slider
- Age group and sex dropdowns
- Reasoning task dropdown
- 8 example cases on the left

**Quick test:**
1. Click any example case (e.g. "Meningitis")
2. Click **▶ Run Clinical Assessment**
3. Wait for the result to appear in the tabs on the right

✅ **Pass if:** Results appear in the Differential Diagnosis tab
❌ **Fail if:** Browser shows "This site can't be reached" — make sure `app.py` is still running

To stop the web UI: go back to the terminal and press **Ctrl+C**

---

### Test 4 — Verify RAM usage

While the web UI is running (after running at least one query), check RAM:

```bash
# In a second terminal
free -h
```

**Expected:**
```
              total        used        free
Mem:           7.6Gi       3.8Gi       3.8Gi
```

Used RAM should be around **3.5–4.0 GB** — well under the 7 GB ADTC ceiling.

Also check with:
```bash
ps aux --sort=-%mem | head -5
```

✅ **Pass if:** Total used RAM is under 7,168 MB
❌ **Fail if:** Used RAM exceeds 7 GB — switch to Q2K model:
```bash
# Edit inference/config.json
# Change model_path to: models/aletheia_q2k.gguf
```

---

### Test 5 — Verify offline operation

**Disable the network adapter:**
- VirtualBox → Devices → Network → uncheck "Connect Network Adapter"

Then run a query:
```bash
python3 run.py --symptoms "altered consciousness, fever, seizures" --duration 2 --age child
```

✅ **Pass if:** Query runs successfully with no internet
❌ **Fail if:** Any network error — there should be none since Aletheia is fully offline

Re-enable network when done:
- VirtualBox → Devices → Network → check "Connect Network Adapter"

---

## PART 5 — RUN THE ADTC PROFILER

The official profiler measures your model's performance in the same
way judges will. Run this to get your self-reported score.

### Step 1 — Install Python 3.11 pip (if not already done)

```bash
python3 --version
# Must show 3.11.x — if not, go back to Part 2 Step 2
```

### Step 2 — Add llama-bench to PATH

The profiler uses `llama-bench` (different from `llama-cli`):

```bash
export PATH="$HOME/llama.cpp/build/bin:$PATH"

# Verify llama-bench exists
llama-bench --version
```

If `llama-bench` is not found, rebuild llama.cpp:
```bash
cmake --build ~/llama.cpp/build --config Release -j$(nproc)
```

### Step 3 — Run the profiler script

```bash
cd ~/Aletheia
bash benchmark/run_adtc_profiler.sh
```

This will:
1. Check Python 3.11 and llama-bench are available
2. Install the official `adtc-profiler` package
3. Run participant-mode profiling against your repo
4. Print your results and scoring breakdown

**Expected output:**
```
╔══════════════════════════════════════════════════════╗
║  Aletheia — ADTC 2026 Official Profiler             ║
║  Mode: Participant (local self-check)                ║
╚══════════════════════════════════════════════════════╝

[ 1/4 ] Checking prerequisites...
  Python 3.11.x ✅
  llama-bench found ✅
  Model: 1.8G ✅

[ 2/4 ] Installing ADTC profiler... ✅

[ 3/4 ] Running profiler in participant mode...

[ 4/4 ] Results:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ADTC 2026 PROFILER RESULTS — Aletheia
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Tokens per second   : X.X
  First token latency : XXXX ms
  Peak RAM            : XXXX MB
  Steady-state RAM    : XXXX MB
  ADTC ceiling        : 7,168 MB
  Margin              : XXXX MB  ✅ PASS

  SCORING FORMULA:
  S = 0.50×Accuracy + 0.30×Throughput + 0.20×Efficiency

  Throughput score    : XX.X/100
  Efficiency score    : XX.X/100

  Results saved: benchmark/submission.json
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ➡  Copy these numbers to the Devpost
     Self-Reported Profiler Score field.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 4 — Read the full results file

```bash
cat ~/Aletheia/benchmark/submission.json | python3 -m json.tool
```

This shows all metrics in detail.

### Step 5 — Fill in the Devpost Self-Reported Profiler Score

From the results, copy:
- **Tokens per second** → Throughput field
- **Peak RAM (MB)** → Memory field
- **First token latency (ms)** → Latency field

---

## PART 6 — RECORD THE DEMO VIDEO

The demo video should show:

1. **Start with the VM open** — show it is Ubuntu 22.04
2. **Open system monitor** — show 8 GB RAM total
3. **Disable internet** (Network → disconnect)
4. **Start the web UI:** `python3 app.py`
5. **Open browser** → http://localhost:7860
6. **Run 3 example cases:**
   - Meningitis (fever, headache, neck stiffness)
   - Eclampsia (seizures in pregnancy, high BP)
   - Severe acute malnutrition (wasting, oedema, child)
7. **Show RAM usage** while model is running: `free -h` in terminal
8. **Show it is offline** — try to open a website, it fails
9. **Run the profiler:** `bash benchmark/run_adtc_profiler.sh`
10. **Show the results** — peak RAM, tokens per second

Keep the video under **3 minutes**. The key moments are:
- No internet + model runs = offline-first ✅
- RAM under 7 GB = ADTC compliant ✅
- Clinical output looks correct = useful ✅

---

## TROUBLESHOOTING

### "No module named apt_pkg" during install.sh

```bash
sudo apt install python3-apt -y
bash install.sh
```

If it still fails, use the manual setup steps in Part 3 Step 5 above.

### "llama-cli not found"
```bash
# Rebuild llama.cpp
cmake -B ~/llama.cpp/build ~/llama.cpp -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=OFF
cmake --build ~/llama.cpp/build --config Release -j$(nproc)
```

### "Model not found"
```bash
ls ~/Aletheia/models/
# Check aletheia_q4km.gguf is there
# If not, copy it from USB or re-download
```

### Web UI won't open in browser
```bash
# Check app.py is still running
# Try: python3 app.py &
# Then open http://127.0.0.1:7860
```

### Inference too slow (>10 min per query)
```bash
# Check CPU cores available
nproc
# Edit inference/config.json — increase "threads" to match nproc
```

### Python version error from profiler
```bash
# Install Python 3.11 explicitly
sudo apt install python3.11 -y
python3.11 -m pip install \
    "git+https://github.com/Africa-Deep-Tech-Foundation/adtc-profiler.git"
python3.11 -m adtc_profiler run \
    --submission ~/Aletheia \
    --mode participant \
    --output ~/Aletheia/benchmark/submission.json \
    --skip-accuracy
```

### RAM exceeds 7 GB
```bash
# Switch to the Q2K fallback model
# Edit inference/config.json:
# "model_path": "/home/aletheia/Aletheia/models/aletheia_q2k.gguf"
# Peak RAM ~2,990 MB — well within budget
```

---

*Aletheia is a research prototype. Not a licensed medical device.*





curl -L \
    "https://drive.google.com/uc?export=download&confirm=t&id=1XZpNCU03C65kGFqJgUMpAWNhJ-Jt2rFO" \
    -o ~/Aletheia/models/aletheia_q4km.gguf


    # Use python3.11 explicitly to run gdown
python3.11 -m gdown "1XZpNCU03C65kGFqJgUMpAWNhJ-Jt2rFO" \
    -O ~/Aletheia/models/aletheia_q4km.gguf


    # Alternative — wget direct download
wget --no-check-certificate \
    "https://drive.google.com/uc?export=download&id=1XZpNCU03C65kGFqJgUMpAWNhJ-Jt2rFO" \
    -O ~/Aletheia/models/aletheia_q4km.gguf