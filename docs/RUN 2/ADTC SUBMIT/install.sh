#!/usr/bin/env bash
# ============================================================
# Aletheia — Install Script
# Ubuntu 22.04 LTS | No GPU required | No internet at runtime
# ============================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLAMA_DIR="$HOME/llama.cpp"
MODEL_DIR="$REPO_DIR/models"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  Aletheia Diagnostic AI — Installation               ║"
echo "║  Soroti University, Uganda                           ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── System dependencies ──────────────────────────────────────
echo "[ 1/5 ] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    build-essential \
    cmake \
    git \
    python3 \
    python3-pip \
    python3-venv \
    wget \
    curl \
    libgomp1

# ── Python dependencies ───────────────────────────────────────
echo "[ 2/5 ] Installing Python packages..."
pip3 install --quiet --upgrade pip
pip3 install --quiet \
    rich \
    typer \
    requests

# ── Build llama.cpp (CPU only) ────────────────────────────────
echo "[ 3/5 ] Building llama.cpp inference engine..."
if [ ! -f "$HOME/llama.cpp/build/bin/llama-cli" ]; then
    if [ ! -d "$LLAMA_DIR" ]; then
        git clone https://github.com/ggerganov/llama.cpp "$LLAMA_DIR" --depth=1 -q
    fi
    cmake -B "$LLAMA_DIR/build" "$LLAMA_DIR" \
        -DCMAKE_BUILD_TYPE=Release \
        -DGGML_CUDA=OFF \
        -Wno-dev \
        -DLLAMA_NATIVE=ON \
        > /dev/null 2>&1
    cmake --build "$LLAMA_DIR/build" \
        --config Release \
        -j"$(nproc)" \
        > /dev/null 2>&1
    echo "    llama.cpp built ✅"
else
    echo "    llama.cpp already built ✅"
fi

# ── Write llama.cpp path to config ───────────────────────────
echo "[ 4/5 ] Writing configuration..."
cat > "$REPO_DIR/inference/config.json" << EOF
{
  "llama_cli": "$HOME/llama.cpp/build/bin/llama-cli",
  "model_path": "$MODEL_DIR/aletheia_q4km.gguf",
  "context_size": 1024,
  "threads": $(nproc),
  "max_tokens": 512,
  "temperature": 0.1
}
EOF
echo "    Config written ✅"

# ── Check model file ──────────────────────────────────────────
echo "[ 5/5 ] Checking model..."
if [ ! -f "$MODEL_DIR/aletheia_q4km.gguf" ]; then
    echo ""
    echo "    ⚠️  Model file not found."
    echo "    Run:  bash models/download_model.sh"
    echo "    Or manually copy aletheia_q4km.gguf to: $MODEL_DIR/"
else
    SIZE=$(du -sh "$MODEL_DIR/aletheia_q4km.gguf" | cut -f1)
    echo "    Model found ($SIZE) ✅"
fi

# ── Done ──────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  Installation complete ✅                            ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Start chatbot:  python3 chat/cli.py                 ║"
echo "║  Single query:   python3 run.py --help               ║"
echo "║  Benchmark:      bash benchmark/benchmark.sh         ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
