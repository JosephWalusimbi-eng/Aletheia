#!/usr/bin/env bash
# ============================================================
# Aletheia - Local inference tuner
#
# Sweeps llama.cpp thread counts with llama-bench, measures generation
# throughput for each, and writes the fastest setting into
# inference/config.json.
#
# Why this matters: llama.cpp does dense matrix work that rarely benefits from
# hyperthreading, so using every logical core is often slower than using only the
# physical ones. The right number is hardware specific, so measure it rather than
# assume it.
#
#   bash benchmark/optimize.sh            measure and apply the best setting
#   bash benchmark/optimize.sh --dry-run  measure only, change nothing
# ============================================================
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$REPO_DIR/inference/config.json"
DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

# ── Locate the model, preferring whatever config.json declares ───────────
MODEL="$REPO_DIR/model/aletheia_q4km.gguf"
if [ -f "$CONFIG" ]; then
    CONFIGURED=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('model_path',''))" "$CONFIG" 2>/dev/null || true)
    [ -n "$CONFIGURED" ] && [ -f "$CONFIGURED" ] && MODEL="$CONFIGURED"
fi
if [ ! -f "$MODEL" ]; then
    echo "Model not found. Run: bash download_model.sh" >&2
    exit 1
fi

BENCH="$HOME/llama.cpp/build/bin/llama-bench"
if [ ! -x "$BENCH" ]; then
    echo "llama-bench not found at $BENCH. Run: bash install.sh" >&2
    exit 1
fi

# ── Candidate thread counts: physical cores, logical cores, and between ──
PHYSICAL=$(lscpu 2>/dev/null | awk -F: '/^Core\(s\) per socket/{gsub(/ /,"",$2);print $2}')
SOCKETS=$(lscpu 2>/dev/null | awk -F: '/^Socket\(s\)/{gsub(/ /,"",$2);print $2}')
LOGICAL=$(nproc)
[ -z "${PHYSICAL:-}" ] && PHYSICAL=$((LOGICAL / 2))
[ -z "${SOCKETS:-}" ] && SOCKETS=1
PHYS_TOTAL=$((PHYSICAL * SOCKETS))
[ "$PHYS_TOTAL" -lt 1 ] && PHYS_TOTAL=1

CANDIDATES=$(printf "%s\n%s\n%s\n%s\n" \
    "$PHYS_TOTAL" "$LOGICAL" "$((PHYS_TOTAL / 2))" "$(( (PHYS_TOTAL + LOGICAL) / 2 ))" \
    | awk '$1 >= 1' | sort -n -u)

echo ""
echo "Aletheia inference tuner"
echo "------------------------"
echo "  CPU            : $(lscpu 2>/dev/null | awk -F: '/^Model name/{sub(/^ +/,"",$2);print $2}')"
echo "  Physical cores : $PHYS_TOTAL"
echo "  Logical cores  : $LOGICAL"
echo "  Model          : $(basename "$MODEL")"
echo "  Testing threads: $(echo $CANDIDATES | tr '\n' ' ')"
echo ""
echo "Each setting runs a short generation benchmark. This takes a few minutes."
echo ""

BEST_T=""
BEST_TPS=0
printf "  %-8s %-14s %s\n" "threads" "gen tok/s" "prompt tok/s"
printf "  %-8s %-14s %s\n" "-------" "---------" "------------"

for T in $CANDIDATES; do
    JSON=$("$BENCH" -m "$MODEL" -p 128 -n 64 -r 2 -t "$T" -ngl 0 -o json 2>/dev/null)
    read -r TG PP <<EOF
$(printf '%s' "$JSON" | python3 -c "
import json,sys
try:
    rows = json.load(sys.stdin)
except Exception:
    print('0 0'); raise SystemExit
tg = pp = 0.0
for r in rows:
    ts = float(r.get('avg_ts', 0) or 0)
    if int(r.get('n_gen', 0) or 0) > 0: tg = ts
    elif int(r.get('n_prompt', 0) or 0) > 0: pp = ts
print(f'{tg:.2f} {pp:.2f}')
")
EOF
    TG=${TG:-0}; PP=${PP:-0}
    printf "  %-8s %-14s %s\n" "$T" "$TG" "$PP"
    if awk "BEGIN{exit !($TG > $BEST_TPS)}"; then
        BEST_TPS=$TG
        BEST_T=$T
    fi
done

echo ""
if [ -z "$BEST_T" ] || [ "$BEST_TPS" = "0" ]; then
    echo "  No usable measurement. Leaving the configuration unchanged."
    exit 1
fi

echo "  Fastest: $BEST_T threads at $BEST_TPS generated tokens per second."

if [ "$DRY_RUN" = "1" ]; then
    echo "  Dry run, configuration not modified."
    exit 0
fi

if [ ! -f "$CONFIG" ]; then
    echo "  No $CONFIG to update. Run bash setup_venv.sh first." >&2
    exit 1
fi

CURRENT=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('threads',''))" "$CONFIG")
if [ "$CURRENT" = "$BEST_T" ]; then
    echo "  inference/config.json already uses $BEST_T threads. Nothing to change."
    exit 0
fi

python3 - "$CONFIG" "$BEST_T" <<'PY'
import json, sys
path, threads = sys.argv[1], int(sys.argv[2])
with open(path) as f:
    cfg = json.load(f)
cfg["threads"] = threads
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
PY
echo "  Updated inference/config.json: threads $CURRENT -> $BEST_T"
echo ""
