#!/usr/bin/env bash

# Aletheia — Model Download Script
# Downloads aletheia_q4km.gguf (~1.8 GB) from Google Drive

set -e

MODEL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_FILE="$MODEL_DIR/aletheia_q4km.gguf"
FALLBACK_FILE="$MODEL_DIR/aletheia_q2k.gguf"

echo ""
echo "Aletheia — Model Download"
echo "──────────────────────────────────────────"

# ── Check if already downloaded ──────────────────────────────
if [ -f "$MODEL_FILE" ]; then
    SIZE=$(du -sh "$MODEL_FILE" | cut -f1)
    echo " Primary model already present ($SIZE)"
    echo "    $MODEL_FILE"
    exit 0
fi

echo "Downloading primary model: aletheia_q4km.gguf (~1.8 GB)"
echo "This may take several minutes depending on your connection."
echo ""

# ── Primary: Google Drive ─────────────────────────────────────
# Replace GDRIVE_FILE_ID with the actual Google Drive file ID
# of aletheia_q4km.gguf after uploading it to Drive
GDRIVE_FILE_ID="https://drive.google.com/file/d/1XZpNCU03C65kGFqJgUMpAWNhJ-Jt2rFO/view?usp=sharing"

if [ "$GDRIVE_FILE_ID" != "https://drive.google.com/file/d/1XZpNCU03C65kGFqJgUMpAWNhJ-Jt2rFO/view?usp=sharing" ]; then
    echo "Downloading from Google Drive..."
    wget --quiet --show-progress \
        "https://drive.google.com/uc?export=download&id=$GDRIVE_FILE_ID" \
        -O "$MODEL_FILE"

    if [ -f "$MODEL_FILE" ]; then
        SIZE=$(du -sh "$MODEL_FILE" | cut -f1)
        echo "Downloaded: aletheia_q4km.gguf ($SIZE)"
        exit 0
    fi
fi

# ── Fallback: HuggingFace Hub ─────────────────────────────────
# Replace with actual HuggingFace repo path if uploaded there
HF_REPO="JosephWalusimbi-eng/aletheia"
HF_FILE="aletheia_q4km.gguf"

echo "Trying HuggingFace Hub..."
if command -v python3 &> /dev/null; then
    python3 - << PYEOF
from huggingface_hub import hf_hub_download
import shutil
try:
    path = hf_hub_download(
        repo_id="$HF_REPO",
        filename="$HF_FILE",
        local_dir="$MODEL_DIR"
    )
    print(f"Downloaded from HuggingFace: {path}")
except Exception as e:
    print(f"HuggingFace download failed: {e}")
    print("Please download the model manually.")
PYEOF
fi

#  Manual instructions 
if [ ! -f "$MODEL_FILE" ]; then
    echo ""
    echo "──────────────────────────────────────────"
    echo " Automatic download failed."
    echo ""
    echo "Manual download instructions:"
    echo "1. Download aletheia_q4km.gguf from:"
    echo "   https://drive.google.com/file/d/1XZpNCU03C65kGFqJgUMpAWNhJ-Jt2rFO/view?usp=sharing"
    echo ""
    echo "2. Copy it to:"
    echo "   $MODEL_DIR/aletheia_q4km.gguf"
    echo ""
    echo "3. Run again to verify:"
    echo "   bash models/download_model.sh"
    echo "──────────────────────────────────────────"
    exit 1
fi
