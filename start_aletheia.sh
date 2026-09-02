#!/usr/bin/env bash
# ============================================================
# Aletheia — Launcher
# Starts the web UI and opens it in the default browser, so a
# clinician never has to touch a terminal.
#
#   bash start_aletheia.sh                    start Aletheia
#   bash start_aletheia.sh --install-shortcut add a desktop icon
# ============================================================
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=7860
URL="http://localhost:${PORT}"

# ── Helpers ───────────────────────────────────────────────────
open_browser() {
    for opener in xdg-open wslview sensible-browser open; do
        if command -v "$opener" >/dev/null 2>&1; then
            "$opener" "$URL" >/dev/null 2>&1 &
            return 0
        fi
    done
    echo "  Could not open a browser automatically — go to $URL"
}

# Port check via Python, so the launcher needs no curl/netcat.
port_is_open() {
    "$1" - <<'PY' 2>/dev/null
import socket, sys
s = socket.socket()
s.settimeout(1)
sys.exit(0 if s.connect_ex(("127.0.0.1", 7860)) == 0 else 1)
PY
}

install_shortcut() {
    local apps="$HOME/.local/share/applications"
    local icon="$REPO_DIR/docs/aletheia_youtube_thumbnail.png"
    mkdir -p "$apps"
    cat > "$apps/aletheia.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Aletheia
Comment=Offline clinical decision support
Exec=bash "$REPO_DIR/start_aletheia.sh"
Icon=$icon
Terminal=false
Categories=Science;MedicalSoftware;
DESKTOP
    chmod +x "$apps/aletheia.desktop"
    command -v update-desktop-database >/dev/null 2>&1 && \
        update-desktop-database "$apps" >/dev/null 2>&1
    echo "  Desktop shortcut installed: $apps/aletheia.desktop"
    echo "  Aletheia should now appear in your applications menu."
}

# ── Desktop shortcut mode ─────────────────────────────────────
if [ "${1:-}" = "--install-shortcut" ]; then
    install_shortcut
    exit 0
fi

echo ""
echo "Aletheia — Offline Clinical Decision Support"
echo "────────────────────────────────────────────"

# ── Locate Python ─────────────────────────────────────────────
if [ -x "$REPO_DIR/venv/bin/python" ]; then
    PY="$REPO_DIR/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PY="$(command -v python3)"
else
    echo "  Python 3 not found. Run: bash setup_venv.sh"
    exit 1
fi

# ── Already running? Just open it. ────────────────────────────
if port_is_open "$PY"; then
    echo "  Already running — opening $URL"
    open_browser
    exit 0
fi

# ── Preflight ─────────────────────────────────────────────────
# The web UI is served by Python's standard library, so there is no package to check.
if [ ! -f "$REPO_DIR/aletheia/server.py" ]; then
    echo "  Missing $REPO_DIR/aletheia/server.py"
    exit 1
fi

export REPO_DIR
MODEL=$("$PY" - <<'PY' 2>/dev/null
import json, os, pathlib
root = pathlib.Path(os.environ["REPO_DIR"])
cfg = root / "inference" / "config.json"
path = ""
if cfg.exists():
    path = json.loads(cfg.read_text()).get("model_path", "")
print(path or str(root / "models" / "aletheia_q4km.gguf"))
PY
)
if [ -n "$MODEL" ] && [ ! -f "$MODEL" ]; then
    echo "  Model file not found: $MODEL"
    echo "  Run: bash download_model.sh"
    exit 1
fi

# ── Start ─────────────────────────────────────────────────────
echo "  Starting Aletheia (this takes a few seconds)..."
"$PY" "$REPO_DIR/aletheia/server.py" &
APP_PID=$!

for _ in $(seq 1 90); do
    if ! kill -0 "$APP_PID" 2>/dev/null; then
        echo "  Aletheia failed to start."
        exit 1
    fi
    if port_is_open "$PY"; then
        echo "  Ready — opening $URL"
        open_browser
        break
    fi
    sleep 1
done

echo "  Press Ctrl+C to stop Aletheia."
wait "$APP_PID"
