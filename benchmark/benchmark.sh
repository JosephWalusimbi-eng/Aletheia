#!/usr/bin/env bash
# ============================================================
# Aletheia — ADTC 2026 Compliance Benchmark
# Measures: RAM usage, inference latency, tokens per second
# Target hardware: Intel Core i5, 8 GB DDR4, Ubuntu 22.04
# ============================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS_FILE="$REPO_DIR/benchmark/results.json"

# The model normally lives in the repo, but inference/config.json is the per-machine
# source of truth (it may point at a copy kept outside the repo). Prefer the repo copy,
# fall back to whatever the config declares.
MODEL="$REPO_DIR/models/aletheia_q4km.gguf"
CONFIG="$REPO_DIR/inference/config.json"
if [ ! -f "$MODEL" ] && [ -f "$CONFIG" ]; then
    CONFIGURED=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('model_path',''))" "$CONFIG" 2>/dev/null || true)
    [ -n "$CONFIGURED" ] && [ -f "$CONFIGURED" ] && MODEL="$CONFIGURED"
fi

# Newer llama.cpp builds turned llama-cli into a conversation-only front end that
# waits for interactive turns instead of completing the prompt and exiting, and ship
# the one-shot completer as llama-completion. Prefer it; fall back on older builds.
LLAMA_BIN_DIR="$HOME/llama.cpp/build/bin"
if [ -f "$LLAMA_BIN_DIR/llama-completion" ]; then
    LLAMA_BIN="$LLAMA_BIN_DIR/llama-completion"
else
    LLAMA_BIN="$LLAMA_BIN_DIR/llama-cli"
fi

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  Aletheia — ADTC 2026 Compliance Benchmark           ║"
echo "╚══════════════════════════════════════════════════════╝"

# ── Checks ────────────────────────────────────────────────────
if [ ! -f "$MODEL" ]; then
    echo "❌  Model not found: $MODEL"
    echo "    Run: bash download_model.sh"
    exit 1
fi

if [ ! -f "$LLAMA_BIN" ]; then
    echo "❌  llama-cli not found: $LLAMA_BIN"
    echo "    Run: bash install.sh"
    exit 1
fi

# ── System info ───────────────────────────────────────────────
echo ""
echo "SYSTEM INFORMATION:"
echo "  OS       : $(lsb_release -d 2>/dev/null | cut -f2 || uname -s)"
echo "  CPU      : $(grep 'model name' /proc/cpuinfo | head -1 | cut -d: -f2 | xargs)"
echo "  Cores    : $(nproc)"
echo "  RAM      : $(free -h | grep Mem | awk '{print $2}')"
echo "  Model    : $(basename $MODEL) ($(du -sh $MODEL | cut -f1))"
echo ""

ADTC_CEILING_MB=7168
RAM_TOTAL_MB=$(free -m | grep Mem | awk '{print $2}')

# ── Test prompts ──────────────────────────────────────────────
declare -a PROMPTS=(
    '### Instruction:\nAnalyze symptoms and provide ranked differential diagnosis.\n\n### Input:\n{"symptoms": ["fever","headache","neck stiffness"],"duration_days": 2,"patient_age_group": "adult","sex": "unknown"}\n\n### Response:\n'
    '### Instruction:\nRecommend diagnostic tests in priority order.\n\n### Input:\n{"symptoms": ["cough","weight loss","night sweats"],"duration_days": 30,"patient_age_group": "adult","sex": "male"}\n\n### Response:\n'
    '### Instruction:\nAssess severity and level of care required.\n\n### Input:\n{"symptoms": ["altered consciousness","seizures","fever"],"duration_days": 1,"patient_age_group": "child","sex": "female"}\n\n### Response:\n'
)

declare -a LABELS=(
    "Meningitis differential"
    "TB test recommendation"
    "Cerebral malaria severity"
)

N_PROMPTS=${#PROMPTS[@]}
TOTAL_ELAPSED=0
TOTAL_TOKENS=0
TOTAL_EVAL_MS=0

echo "BENCHMARK RUNS ($N_PROMPTS prompts):"
echo "──────────────────────────────────────────────────────"

for i in "${!PROMPTS[@]}"; do
    LABEL="${LABELS[$i]}"
    PROMPT="${PROMPTS[$i]}"

    printf "  [%d/%d] %-35s" "$((i+1))" "$N_PROMPTS" "$LABEL"

    # Measure RAM before
    RAM_BEFORE=$(free -m | grep Mem | awk '{print $3}')

    # Run inference. llama.cpp writes its own timing report to stderr — keep it, it is
    # the only accurate source of generated-token counts and generation throughput.
    STDERR_FILE=$(mktemp)
    START=$(date +%s%N)
    OUTPUT=$("$LLAMA_BIN" \
        -m "$MODEL" \
        -p "$(printf "$PROMPT")" \
        -n 256 \
        -c 1024 \
        -t "$(nproc)" \
        --temp 0.1 \
        --no-display-prompt \
        -ngl 0 \
        2>"$STDERR_FILE")
    END=$(date +%s%N)

    # Measure RAM after
    RAM_AFTER=$(free -m | grep Mem | awk '{print $3}')
    RAM_USED=$((RAM_AFTER - RAM_BEFORE + 900))  # +900MB OS baseline

    ELAPSED_MS=$(( (END - START) / 1000000 ))
    ELAPSED_S=$(echo "scale=2; $ELAPSED_MS / 1000" | bc)

    # Real generated-token count and generation rate, taken from llama.cpp's own
    # "eval time" line (the prompt-eval line is a different, much faster figure).
    # Counting words instead understates throughput by roughly 4x.
    EVAL_LINE=$(grep " eval time =" "$STDERR_FILE" | grep -v "prompt eval time" | tail -1)
    TOKEN_COUNT=$(echo "$EVAL_LINE" | sed -n 's|.* eval time =[^/]*/ *\([0-9]*\) runs.*|\1|p')
    EVAL_MS=$(echo "$EVAL_LINE" | sed -n 's|.* eval time = *\([0-9]*\)\.[0-9]* ms.*|\1|p')
    TPS=$(echo "$EVAL_LINE" | sed -n 's|.*, *\([0-9.]*\) tokens per second.*|\1|p')
    rm -f "$STDERR_FILE"

    # Fall back to the wall-clock word estimate if llama.cpp changed its report format.
    if [ -z "$TOKEN_COUNT" ]; then
        TOKEN_COUNT=$(echo "$OUTPUT" | wc -w)
        EVAL_MS=$ELAPSED_MS
        TPS=$(echo "scale=1; $TOKEN_COUNT / ($ELAPSED_MS / 1000)" | bc 2>/dev/null || echo "?")
    fi

    TOTAL_TOKENS=$((TOTAL_TOKENS + TOKEN_COUNT))
    TOTAL_EVAL_MS=$((TOTAL_EVAL_MS + EVAL_MS))
    TOTAL_ELAPSED=$((TOTAL_ELAPSED + ELAPSED_MS))

    PASS="✅ PASS"
    if [ "$RAM_USED" -gt "$ADTC_CEILING_MB" ]; then
        PASS="❌ FAIL"
    fi

    echo " ${ELAPSED_S}s | ~${RAM_USED}MB RAM | ${TPS} t/s | $PASS"
done

echo "──────────────────────────────────────────────────────"

# ── Summary ───────────────────────────────────────────────────
AVG_ELAPSED_S=$(echo "scale=2; $TOTAL_ELAPSED / $N_PROMPTS / 1000" | bc)
AVG_TPS=$(echo "scale=1; $TOTAL_TOKENS / ($TOTAL_EVAL_MS / 1000)" | bc 2>/dev/null || echo "?")
MODEL_SIZE_MB=$(du -m "$MODEL" | cut -f1)
EST_RAM_MB=$((MODEL_SIZE_MB + 900 + 400 + 300 + 200))

echo ""
echo "SUMMARY:"
echo "  Average latency    : ${AVG_ELAPSED_S}s per query"
echo "  Average throughput : ${AVG_TPS} tokens/second"
echo "  Model file size    : ${MODEL_SIZE_MB} MB"
echo "  Est. peak RAM      : ~${EST_RAM_MB} MB"
echo "  ADTC ceiling       : ${ADTC_CEILING_MB} MB"
echo "  Margin             : $((ADTC_CEILING_MB - EST_RAM_MB)) MB"
echo ""

if [ "$EST_RAM_MB" -lt "$ADTC_CEILING_MB" ]; then
    echo "  ADTC 2026 Memory   : ✅ PASS"
else
    echo "  ADTC 2026 Memory   : ❌ FAIL"
fi

echo ""
echo "  Internet required  : None"
echo "  GPU required       : None (CPU only)"
echo "  OS tested          : $(lsb_release -d 2>/dev/null | cut -f2 || uname -s)"
echo ""

# ── Save results JSON ─────────────────────────────────────────
cat > "$RESULTS_FILE" << JSON
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "model": "aletheia_q4km.gguf",
  "system": {
    "cpu": "$(grep 'model name' /proc/cpuinfo | head -1 | cut -d: -f2 | xargs)",
    "cores": $(nproc),
    "ram_total_mb": $RAM_TOTAL_MB,
    "os": "$(lsb_release -d 2>/dev/null | cut -f2 || uname -s)"
  },
  "performance": {
    "avg_latency_seconds": $AVG_ELAPSED_S,
    "avg_tokens_per_second": "$AVG_TPS",
    "n_prompts_tested": $N_PROMPTS
  },
  "adtc_compliance": {
    "model_size_mb": $MODEL_SIZE_MB,
    "estimated_peak_ram_mb": $EST_RAM_MB,
    "ceiling_mb": $ADTC_CEILING_MB,
    "margin_mb": $((ADTC_CEILING_MB - EST_RAM_MB)),
    "internet_required": false,
    "gpu_required": false,
    "pass": $([ "$EST_RAM_MB" -lt "$ADTC_CEILING_MB" ] && echo "true" || echo "false")
  }
}
JSON

echo "Results saved: $RESULTS_FILE"
echo ""
