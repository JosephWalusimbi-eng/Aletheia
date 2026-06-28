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
| Name | VMAletheia | Any name |
| Type | Linux | — |
| Version | Ubuntu 22.04 LTS (64-bit) | ADTC standard OS |
| RAM | **8192 MB (8 GB)** | Matches ADTC spec exactly |
| CPU cores | **4** | Simulates i5 10th gen |
| Storage | **60 GB** (VDI, dynamically allocated) | Model = 1.8 GB + OS + packages |
| 3D Acceleration | **OFF** | No GPU — ADTC spec |
| Network | NAT | Internet for setup only |

**Step by step in VirtualBox:**
1. Click **New**
2. Name: `VMAletheia` → Type: Linux → Version: Ubuntu (64-bit) → Next
3. Memory: drag to **8192 MB** → Next
4. Create a virtual hard disk → VDI → Dynamically allocated → **60 GB** → Create
5. Right-click the VM → **Settings**
6. System → Processor → set to **4 CPUs**
7. Display → Screen → uncheck **Enable 3D Acceleration**
8. Click OK

> ⚠️ **Store the VM on C: drive** (e.g. `C:\VMs\VMAletheia`), not on an
> external or secondary drive (D:, E:). Storing on external drives causes
> "Failed to save the settings" errors when adding shared folders.
> If you already created the VM on another drive, use the resize process
> in the Troubleshooting section to move it.

> ⚠️ **Start with 60 GB** — not 25 GB. The model file (1.80 GB) +
> llama.cpp build (~500 MB) + Ubuntu base (~10 GB) + Python packages
> fills a 25 GB disk completely, causing the VM to freeze and the
> terminal to stop opening.

**Download Ubuntu 22.04 LTS:**
```
https://releases.ubuntu.com/22.04/ubuntu-22.04.5-desktop-amd64.iso
```

**Boot from ISO:**
1. Settings → Storage → click the empty CD icon
2. Click the disk icon on the right → Choose disk file → select the ISO
3. Start the VM
4. Choose **Install Ubuntu** → Minimal installation → Erase disk and install
5. Set username and password
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

After Ubuntu boots for the first time, open a terminal (Ctrl+Alt+T).

### Step 1 — Update the system

```bash
sudo apt update && sudo apt upgrade -y
```

### Step 2 — Install Python 3.11

Ubuntu 22.04 ships with Python 3.10 but the ADTC profiler requires 3.11.
The packages `python3.11-pip` and `python3.11-venv` do **not exist** on
Ubuntu 22.04 — use the deadsnakes PPA instead:

```bash
# Add deadsnakes PPA
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update

# Install Python 3.11 and venv
sudo apt install python3.11 python3.11-venv -y

# Install pip for 3.11 separately
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

> ⚠️ Do NOT run `sudo apt install python3.11-pip` — this package does
> not exist on Ubuntu 22.04 and will give "Unable to locate package" error.
> Use the curl method above instead.

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

This gets all scripts, configs, and the full repo structure instantly.
No need for shared folders or USB drives.

### Step 2 — Download the model file from Google Drive

The model file (`aletheia_q4km.gguf`, 1.80 GB) is too large for GitHub.
Download it directly from Google Drive inside the VM.

```bash
# Install gdown
pip3 install gdown

# Download using the model file ID
python3.11 -m gdown "1XZpNCU03C65kGFqJgUMpAWNhJ-Jt2rFO" \
    -O ~/Aletheia/models/aletheia_q4km.gguf
```

If gdown gives a "permission denied" or quota error, use the fuzzy method:
```bash
python3.11 -m gdown --fuzzy \
    "https://drive.google.com/file/d/1XZpNCU03C65kGFqJgUMpAWNhJ-Jt2rFO/view?usp=sharing" \
    -O ~/Aletheia/models/aletheia_q4km.gguf
```

**Verify the download:**
```bash
ls -lh ~/Aletheia/models/aletheia_q4km.gguf
# Should show: ~1.8 GB
```

> ℹ️ gdown may show `1.93 G` while Google Drive shows `1.8 GB` — this
> is normal. They are the same file in different units (GiB vs GB).

### Step 3 — Run the install script

```bash
cd ~/Aletheia
bash install.sh
```

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

If `bash install.sh` shows:
```
ModuleNotFoundError: No module named 'apt_pkg'
E: Problem executing scripts APT::Update::Post-Invoke-Success
```

Fix:
```bash
sudo apt install python3-apt -y
bash install.sh
```

If it still fails, bypass install.sh and set up manually:

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
USERNAME=$(whoami)
mkdir -p ~/Aletheia/inference
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

Verify the config:
```bash
cat ~/Aletheia/inference/config.json
```

### Step 4 — Fix Pillow (required for Gradio web UI)

Before running the web UI, upgrade Pillow to avoid an import error:

```bash
pip3 install --upgrade Pillow
```

If Gradio still fails after upgrading:
```bash
pip3 install --upgrade --force-reinstall Pillow gradio
```

---

## PART 4 — TEST FUNCTIONALITY

Run each test in order.

### Test 1 — Single query (CLI)

Confirms model loads and inference works:

```bash
cd ~/Aletheia

python3 run.py \
    --symptoms "fever, headache, neck stiffness" \
    --duration 2 \
    --age adult
```

**Takes 2–5 minutes on first run.** Expected output:
```
Aletheia Diagnostic AI
────────────────────────────────────────
Symptoms : fever, headache, neck stiffness
Duration : 2 day(s)
Task     : initial_differential
────────────────────────────────────────
Running inference...

[142.3s]

RANKED DIFFERENTIAL DIAGNOSIS:
  1. Bacterial Meningitis    55%  ██████████  [Critical]
  2. Viral Meningitis        20%  ████        [High]
  3. Cerebral Malaria        15%  ███         [Critical]
  4. Severe Typhoid           5%  █           [High]
```

✅ **Pass if:** Ranked differentials appear in output
❌ **Fail if:** "Model not found" — check Step 2 model download

---

### Test 2 — Interactive chatbot (CLI)

```bash
python3 chat/cli.py
```

Enter symptoms one by one, press blank line when done.
Select task `1` for differential diagnosis.
Type `n` to exit when asked "Assess another patient?"

✅ **Pass if:** Formatted table of diagnoses appears

---

### Test 3 — Web UI (Gradio)

```bash
python3 app.py
```

Open Firefox in the VM → go to **http://localhost:7860**

1. Click any example case
2. Click **▶ Run Clinical Assessment**
3. Wait for results in the tabs on the right

✅ **Pass if:** Results appear in Differential Diagnosis tab
❌ **Fail if:** "ImportError: cannot import name '_imaging' from PIL"
   → Run: `pip3 install --upgrade Pillow` then try again

To stop: press **Ctrl+C** in the terminal

---

### Test 4 — Verify RAM usage

While web UI is running after at least one query:

```bash
free -h
```

Used RAM should be around **3.5–4.0 GB** — under the 7 GB ADTC ceiling.

✅ **Pass if:** Total used RAM under 7,168 MB

---

### Test 5 — Verify offline operation

Disconnect network: VirtualBox → Devices → Network → uncheck "Connect Network Adapter"

```bash
python3 run.py --symptoms "altered consciousness, fever, seizures" --duration 2 --age child
```

✅ **Pass if:** Query runs successfully with no internet

Re-enable network when done.

---

## PART 5 — RUN THE ADTC PROFILER

### Step 1 — Add llama-bench to PATH

The profiler uses `llama-bench` (different from `llama-cli`):

```bash
export PATH="$HOME/llama.cpp/build/bin:$PATH"

# Verify
llama-bench --version
```

To make this permanent:
```bash
echo 'export PATH="$HOME/llama.cpp/build/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Step 2 — Run the profiler

```bash
cd ~/Aletheia
bash benchmark/run_adtc_profiler.sh
```

This will:
1. Check Python 3.11 and llama-bench are available
2. Install the official `adtc-profiler` package from GitHub
3. Run participant-mode profiling against your repo
4. Print results and scoring breakdown
5. Save results to `benchmark/submission.json`

### Step 3 — Read the full results

```bash
cat ~/Aletheia/benchmark/submission.json | python3 -m json.tool
```

### Step 4 — Fill in Devpost Self-Reported Profiler Score

Copy from results:
- **Tokens per second** → Throughput field
- **Peak RAM (MB)** → Memory field
- **First token latency (ms)** → Latency field

---

## PART 6 — RECORD THE DEMO VIDEO

1. Show VM open — Ubuntu 22.04
2. Open system monitor — show 8 GB RAM total
3. Disconnect internet
4. Run: `python3 app.py`
5. Open browser → http://localhost:7860
6. Run 3 clinical cases (meningitis, eclampsia, SAM)
7. Show RAM: `free -h` in second terminal
8. Show offline — try opening a website, it fails
9. Run: `bash benchmark/run_adtc_profiler.sh`
10. Show results

Keep under **3 minutes**.

---

## TROUBLESHOOTING

### VM terminal won't open / VM freezes

**Cause:** Disk is completely full.
**Fix:** Shut down the VM and extend the disk (see below).

### Extending the VM disk (from 25 GB to 60 GB)

**Step 1 — Copy the disk at larger size:**
1. In VirtualBox → Tools → Media (or File → Virtual Media Manager)
2. Select your `.vdi` file → click **Copy**
3. Set size to **60 GB** → VDI format → Finish
4. Note the path of the new copy (e.g. `VMAletheia_copy.vdi`)

**Step 2 — Attach the new disk:**
1. VM → Settings → Storage
2. Under Controller: SATA, remove the old disk
3. Click the + icon → Hard disk → Add → browse to `VMAletheia_copy.vdi`
4. Click OK

**Step 3 — Extend partition inside Ubuntu:**
```bash
sudo apt install gparted -y
sudo gparted
```
In GParted: right-click main partition → Resize/Move → drag to fill
unallocated space → Apply → reboot.

```bash
sudo reboot
df -h   # verify ~58 GB available
```

### "No module named apt_pkg"
```bash
sudo apt install python3-apt -y
bash install.sh
```

### "Unable to locate package python3.11-pip"
```bash
# Use curl method instead
curl -sS https://bootstrap.pypa.io/get-pip.py | sudo python3.11
```

### "ImportError: cannot import name '_imaging' from PIL"
```bash
pip3 install --upgrade Pillow
# Or if that fails:
pip3 install --upgrade --force-reinstall Pillow gradio
```

### "llama-cli not found"
```bash
cmake -B ~/llama.cpp/build ~/llama.cpp \
    -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=OFF
cmake --build ~/llama.cpp/build --config Release -j$(nproc)
```

### "llama-bench not found" (profiler)
```bash
export PATH="$HOME/llama.cpp/build/bin:$PATH"
llama-bench --version
```

### gdown shows 1.93G but Drive shows 1.8GB
Normal — same file, different units (GiB vs GB). No problem.

### RAM exceeds 7 GB
```bash
# Switch to Q2K fallback model in config
sed -i 's/aletheia_q4km.gguf/aletheia_q2k.gguf/' \
    ~/Aletheia/inference/config.json
# Peak RAM ~2,990 MB — well within budget
```

### Pull latest changes from GitHub
```bash
cd ~/Aletheia
git pull
```

### VirtualBox "Failed to save settings" error
Store the VM on C: drive, not an external drive.
Or use the disk copy method above.

---

*Aletheia is a research prototype. Not a licensed medical device.*
