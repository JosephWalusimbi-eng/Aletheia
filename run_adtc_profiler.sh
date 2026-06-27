#!/usr/bin/env bash
# ============================================================
# Aletheia — ADTC 2026 Official Profiler Integration
# Runs the official Africa Deep Tech Challenge profiler against
# the Aletheia model and records the self-reported score
# ============================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL="$REPO_DIR/models/aletheia_q4km.gguf"
PROFILER_DIR="$HOME/adtc-profiler"
RESULTS_DIR="$REPO_DIR/benchmark"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  Aletheia — ADTC 2026 Official Profiler              ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Clone the official profiler ──────────────────────
if [ ! -d "$PROFILER_DIR" ]; then
    echo "[ 1/4 ] Cloning official ADTC profiler..."
    git clone https://github.com/Africa-Deep-Tech-Foundation/adtc-profiler.git \
        "$PROFILER_DIR" --depth=1 -q
    echo "  Profiler cloned ✅"
else
    echo "[ 1/4 ] Profiler already cloned — pulling latest..."
    cd "$PROFILER_DIR" && git pull -q
    echo "  Profiler updated ✅"
fi

# ── Step 2: Check model exists ────────────────────────────────
echo "[ 2/4 ] Checking model..."
if [ ! -f "$MODEL" ]; then
    echo "  ❌  Model not found: $MODEL"
    echo "  Run: bash models/download_model.sh"
    exit 1
fi
SIZE=$(du -sh "$MODEL" | cut -f1)
echo "  Model: $MODEL ($SIZE) ✅"

# ── Step 3: Install profiler dependencies ────────────────────
echo "[ 3/4 ] Installing profiler dependencies..."
if [ -f "$PROFILER_DIR/requirements.txt" ]; then
    pip3 install -r "$PROFILER_DIR/requirements.txt" -q
    echo "  Dependencies installed ✅"
else
    pip3 install psutil py-cpuinfo -q
    echo "  Base dependencies installed ✅"
fi

# ── Step 4: Run the profiler ──────────────────────────────────
echo "[ 4/4 ] Running ADTC profiler..."
echo ""

cd "$PROFILER_DIR"

# Try common profiler entry points
if [ -f "profiler.py" ]; then
    python3 profiler.py \
        --model "$MODEL" \
        --output "$RESULTS_DIR/adtc_profiler_results.json" \
        --format gguf \
        --threads "$(nproc)" \
        --context 1024
elif [ -f "run_profiler.py" ]; then
    python3 run_profiler.py \
        --model "$MODEL" \
        --output "$RESULTS_DIR/adtc_profiler_results.json"
elif [ -f "main.py" ]; then
    python3 main.py \
        --model "$MODEL" \
        --output "$RESULTS_DIR/adtc_profiler_results.json"
else
    echo "  ⚠️  Could not find profiler entry point."
    echo "  Check $PROFILER_DIR for the correct script name."
    echo "  Then run it manually with:"
    echo "    python3 <script>.py --model $MODEL"
    echo ""
    echo "  Running manual benchmark as fallback..."
    bash "$REPO_DIR/benchmark/benchmark.sh"
    exit 0
fi

# ── Show results ──────────────────────────────────────────────
echo ""
if [ -f "$RESULTS_DIR/adtc_profiler_results.json" ]; then
    echo "ADTC Profiler Results:"
    cat "$RESULTS_DIR/adtc_profiler_results.json"
    echo ""
    echo "✅  Results saved: $RESULTS_DIR/adtc_profiler_results.json"
    echo ""
    echo "Use these numbers for the ADTC Self-Reported Profiler Score"
    echo "on the Devpost submission form."
else
    echo "⚠️  No results file found. Check profiler output above."
fi
