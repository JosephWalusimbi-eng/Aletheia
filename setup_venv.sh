#!/usr/bin/env bash
# ============================================================
# Aletheia — Python 3.11 Virtual Environment Setup
# Run this ONCE after cloning the repo.
# After setup, always activate with: source venv/bin/activate
# ============================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_DIR/venv"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  Aletheia — Python 3.11 Virtual Environment Setup    ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Check Python 3.11 ─────────────────────────────────────────
echo "[ 1/5 ] Checking Python 3.11..."
if ! command -v python3.11 &> /dev/null; then
    echo "  ❌  Python 3.11 not found. Install it first:"
    echo ""
    echo "  sudo add-apt-repository ppa:deadsnakes/ppa -y"
    echo "  sudo apt update"
    echo "  sudo apt install python3.11 python3.11-venv -y"
    echo "  curl -sS https://bootstrap.pypa.io/get-pip.py | sudo python3.11"
    echo ""
    exit 1
fi
PYVER=$(python3.11 --version)
echo "  $PYVER ✅"

# ── Create venv ───────────────────────────────────────────────
echo "[ 2/5 ] Creating virtual environment at $VENV_DIR..."
if [ -d "$VENV_DIR" ]; then
    echo "  venv already exists — skipping creation"
else
    python3.11 -m venv "$VENV_DIR"
    echo "  venv created ✅"
fi

# ── Activate and upgrade pip ──────────────────────────────────
echo "[ 3/5 ] Activating venv and upgrading pip..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip --quiet
echo "  pip upgraded ✅"

# ── Install dependencies ──────────────────────────────────────
echo "[ 4/5 ] Installing Python dependencies..."
pip install -r "$REPO_DIR/requirements.txt" --quiet
echo "  All packages installed ✅"

# ── Install system dependencies and build llama.cpp ──────────
echo "[ 5/5 ] Installing system dependencies and building llama.cpp..."

# System packages
sudo apt-get install -y -qq \
    build-essential \
    cmake \
    git \
    libgomp1 \
    curl

# Build llama.cpp if not already built
LLAMA_BIN="$HOME/llama.cpp/build/bin/llama-cli"
if [ ! -f "$LLAMA_BIN" ]; then
    echo "  Cloning llama.cpp..."
    git clone https://github.com/ggerganov/llama.cpp "$HOME/llama.cpp" \
        --depth=1 -q
    echo "  Building llama.cpp (3–5 minutes)..."
    cmake -B "$HOME/llama.cpp/build" "$HOME/llama.cpp" \
        -DCMAKE_BUILD_TYPE=Release \
        -DGGML_CUDA=OFF \
        -Wno-dev \
        > /dev/null 2>&1
    cmake --build "$HOME/llama.cpp/build" \
        --config Release \
        -j"$(nproc)" \
        > /dev/null 2>&1
    echo "  llama.cpp built ✅"
else
    echo "  llama.cpp already built ✅"
fi

# Add llama-bench and llama-cli to PATH permanently
BASHRC="$HOME/.bashrc"
if ! grep -q "llama.cpp/build/bin" "$BASHRC"; then
    echo "export PATH=\"\$HOME/llama.cpp/build/bin:\$PATH\"" >> "$BASHRC"
    echo "  PATH updated for llama.cpp binaries ✅"
fi
export PATH="$HOME/llama.cpp/build/bin:$PATH"

# ── Write config ──────────────────────────────────────────────
# Paths are derived from $HOME and the repo location, so the config stays correct
# no matter where the repo was cloned or what the account is called.
mkdir -p "$REPO_DIR/inference"
# llama.cpp does dense matrix work that does not benefit from hyperthreading, so
# default to physical cores rather than nproc. On a 4 core / 8 thread laptop this
# measured 7.10 tok/s at 4 threads against 4.14 tok/s at 8. Run
# `bash benchmark/optimize.sh` to measure and tune this for your own machine.
PHYSICAL_CORES=$(lscpu 2>/dev/null | awk -F: '/^Core\(s\) per socket/{gsub(/ /,"",$2);print $2}')
SOCKETS=$(lscpu 2>/dev/null | awk -F: '/^Socket\(s\)/{gsub(/ /,"",$2);print $2}')
[ -z "${PHYSICAL_CORES:-}" ] && PHYSICAL_CORES=$(( $(nproc) / 2 ))
[ -z "${SOCKETS:-}" ] && SOCKETS=1
THREADS=$((PHYSICAL_CORES * SOCKETS))
[ "$THREADS" -lt 1 ] && THREADS=$(nproc)

cat > "$REPO_DIR/inference/config.json" << CONFIGEOF
{
  "llama_cli": "$HOME/llama.cpp/build/bin/llama-cli",
  "model_path": "$REPO_DIR/model/aletheia_q4km.gguf",
  "context_size": 1024,
  "threads": $THREADS,
  "max_tokens": 512,
  "temperature": 0.1
}
CONFIGEOF
echo "  Config written ✅"

# ── Check model ───────────────────────────────────────────────
MODEL="$REPO_DIR/model/aletheia_q4km.gguf"
if [ ! -f "$MODEL" ]; then
    echo ""
    echo "  ⚠️  Model file not found — download it:"
    echo "  source venv/bin/activate"
    echo "  bash download_model.sh"
else
    SIZE=$(du -sh "$MODEL" | cut -f1)
    echo "  Model: $SIZE ✅"
fi

# ── Done ──────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  Setup complete ✅                                    ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  IMPORTANT: Always activate the venv before use:     ║"
echo "║                                                       ║"
echo "║    source venv/bin/activate                          ║"
echo "║                                                       ║"
echo "║  Then run:                                            ║"
echo "║    bash start_aletheia.sh  ← Web UI                  ║"
echo "║    python3 cli.py          ← Interactive terminal    ║"
echo "║    python3 run.py --help   ← Single query            ║"
echo "║    bash benchmark/run_adtc_profiler.sh               ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "To deactivate the venv when done: deactivate"
echo ""
