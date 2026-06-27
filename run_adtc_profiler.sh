#!/usr/bin/env bash
# ============================================================
# Aletheia — ADTC 2026 Official Profiler (Participant Mode)
# Uses: github.com/Africa-Deep-Tech-Foundation/adtc-profiler
#
# Run this on the ADTC standard laptop (Ubuntu 22.04, 8GB RAM)
# to generate your self-reported profiler score for Devpost.
#
# Usage:
#   bash benchmark/run_adtc_profiler.sh
# ============================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS_DIR="$REPO_DIR/benchmark"
OUTPUT_FILE="$RESULTS_DIR/submission.json"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  Aletheia — ADTC 2026 Official Profiler             ║"
echo "║  Mode: Participant (local self-check)                ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Prerequisites check ───────────────────────────────────────
echo "[ 1/4 ] Checking prerequisites..."

# Python >= 3.11 required by profiler
PYTHON_VER=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
PYTHON_MAJOR=$(echo $PYTHON_VER | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VER | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo "  ⚠️  Python $PYTHON_VER detected — profiler requires Python >= 3.11"
    echo "  Install Python 3.11: sudo apt install python3.11"
    echo "  Then re-run this script."
    exit 1
fi
echo "  Python $PYTHON_VER ✅"

# llama-bench must be on PATH (part of llama.cpp build)
LLAMA_BENCH="$HOME/llama.cpp/build/bin/llama-bench"
if [ ! -f "$LLAMA_BENCH" ]; then
    echo "  ❌  llama-bench not found at $LLAMA_BENCH"
    echo "  Run: bash install.sh first to build llama.cpp"
    exit 1
fi
# Add to PATH for profiler to find it
export PATH="$HOME/llama.cpp/build/bin:$PATH"
echo "  llama-bench found ✅"

# Model file check
MODEL="$REPO_DIR/models/aletheia_q4km.gguf"
if [ ! -f "$MODEL" ]; then
    echo "  ❌  Model not found: $MODEL"
    echo "  Run: bash models/download_model.sh"
    exit 1
fi
echo "  Model: $(du -sh $MODEL | cut -f1) ✅"

# ── Install profiler ──────────────────────────────────────────
echo ""
echo "[ 2/4 ] Installing ADTC profiler..."
pip3 install --quiet \
    "git+https://github.com/Africa-Deep-Tech-Foundation/adtc-profiler.git"
echo "  adtc-profiler installed ✅"

# ── Run profiler (participant mode) ───────────────────────────
echo ""
echo "[ 3/4 ] Running profiler in participant mode..."
echo "  Submission: $REPO_DIR"
echo "  Output: $OUTPUT_FILE"
echo "  This may take 5–10 minutes on first run..."
echo ""

adtc-profiler run \
    --submission "$REPO_DIR" \
    --mode participant \
    --output "$OUTPUT_FILE" \
    --skip-accuracy

# ── Show results ──────────────────────────────────────────────
echo ""
echo "[ 4/4 ] Results:"
echo ""

if [ -f "$OUTPUT_FILE" ]; then
    # Pretty print key metrics
    python3 - << PYEOF
import json

with open('$OUTPUT_FILE') as f:
    data = json.load(f)

print("━"*55)
print("  ADTC 2026 PROFILER RESULTS — Aletheia")
print("━"*55)

# Throughput
t = data.get('throughput', {})
tps = t.get('tokens_per_second_generation', 'N/A')
ttft = t.get('first_token_latency_ms', 'N/A')
print(f"  Tokens per second   : {tps}")
print(f"  First token latency : {ttft} ms")

# Memory
m = data.get('memory', {})
peak = m.get('peak_rss_mb', 'N/A')
steady = m.get('steady_state_rss_mb', 'N/A')
print(f"  Peak RAM            : {peak} MB")
print(f"  Steady-state RAM    : {steady} MB")
print(f"  ADTC ceiling        : 7,168 MB")
if isinstance(peak, (int, float)):
    margin = 7168 - peak
    verdict = "✅ PASS" if peak < 7168 else "❌ FAIL"
    print(f"  Margin              : {margin:.0f} MB  {verdict}")

# CPU
c = data.get('cpu', {})
util = c.get('avg_utilization_pct', 'N/A')
print(f"  CPU utilisation     : {util}%")

# Scoring formula preview
print()
print("  SCORING FORMULA:")
print("  S = 0.50×Accuracy + 0.30×Throughput + 0.20×Efficiency")
print()
TPS_REF = 15.0
RAM_LIMIT_GB = 7.0
if isinstance(tps, (int, float)):
    s_perf = min(tps / TPS_REF, 1.0) * 100
    print(f"  Throughput score    : {s_perf:.1f}/100  (TPS={tps:.1f}, ref={TPS_REF})")
if isinstance(peak, (int, float)):
    peak_gb = peak / 1024
    s_eff = max(0, (RAM_LIMIT_GB - peak_gb) / RAM_LIMIT_GB) * 100
    print(f"  Efficiency score    : {s_eff:.1f}/100  (peak={peak_gb:.2f} GB)")

print()
print("  Results saved: $OUTPUT_FILE")
print("━"*55)
print()
print("  ➡  Copy these numbers to the Devpost")
print("     Self-Reported Profiler Score field.")
print("━"*55)
PYEOF
else
    echo "  ⚠️  Output file not found: $OUTPUT_FILE"
    echo "  Check profiler output above for errors."
fi
