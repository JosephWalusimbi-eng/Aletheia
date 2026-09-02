#!/usr/bin/env bash
# download_model.sh
# Downloads the Aletheia GGUF model weights from Google Drive to the model/ directory.
# Idempotent — safe to run multiple times (skips download if file already exists).
#
# Google Drive requires gdown to bypass the virus-scan confirmation page that
# Google inserts for files over ~100 MB. curl and wget alone will silently
# download that HTML page instead of the actual model file.

set -euo pipefail

MODEL_DIR="model"
MODEL_FILE="aletheia_q4km.gguf"
GDRIVE_FILE_ID="1XZpNCU03C65kGFqJgUMpAWNhJ-Jt2rFO"

# ── Skip if already downloaded ────────────────────────────────
mkdir -p "${MODEL_DIR}"

if [ -f "${MODEL_DIR}/${MODEL_FILE}" ]; then
    echo "Model already present: ${MODEL_DIR}/${MODEL_FILE} — skipping download."
    exit 0
fi

# ── Ensure gdown is available ─────────────────────────────────
if ! command -v gdown &>/dev/null; then
    echo "gdown not found — installing..."
    pip install -q "gdown>=5.1.0"
fi

# ── Download from Google Drive ────────────────────────────────
echo "Downloading ${MODEL_FILE} from Google Drive (file ID: ${GDRIVE_FILE_ID})..."
echo "This may take several minutes depending on file size and connection speed."

gdown --id "${GDRIVE_FILE_ID}" -O "${MODEL_DIR}/${MODEL_FILE}"

# ── Verify the download ───────────────────────────────────────
if [ ! -s "${MODEL_DIR}/${MODEL_FILE}" ]; then
    echo "ERROR: Downloaded file is empty — the download likely failed."
    echo "Check that the file is shared as 'Anyone with the link can view' on Google Drive."
    rm -f "${MODEL_DIR}/${MODEL_FILE}"
    exit 1
fi

# Read first 4 bytes and check for GGUF magic
MAGIC=$(python3 -c "
with open('${MODEL_DIR}/${MODEL_FILE}', 'rb') as f:
    b = f.read(4)
print(b.decode('ascii', errors='replace'))
" 2>/dev/null || echo "")

if [ "${MAGIC}" != "GGUF" ]; then
    echo "ERROR: Downloaded file is not a valid GGUF model."
    echo "       First bytes: '${MAGIC}' (expected 'GGUF')"
    echo "       This usually means Google Drive returned an error page instead of the file."
    echo "       Possible causes:"
    echo "         - The file is not shared publicly (share it as 'Anyone with the link')"
    echo "         - The daily download quota for this file has been exceeded"
    echo "         - The file ID is incorrect"
    rm -f "${MODEL_DIR}/${MODEL_FILE}"
    exit 1
fi

FILESIZE=$(du -sh "${MODEL_DIR}/${MODEL_FILE}" | cut -f1)
echo ""
echo "Done: ${MODEL_DIR}/${MODEL_FILE} (${FILESIZE})"
