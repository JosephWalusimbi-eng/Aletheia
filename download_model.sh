#!/usr/bin/env bash
# download_model.sh
# Downloads the Aletheia GGUF model weights to the model/ directory.
# Idempotent: safe to run repeatedly, it skips the download when the file is
# already present and complete.
#
# Weights are hosted on Hugging Face, which serves them over plain HTTPS with no
# credentials and supports range requests. That lets curl resume a partial
# transfer instead of starting over, which matters on the intermittent
# connections this project is built for.

set -euo pipefail

MODEL_DIR="model"
MODEL_FILE="aletheia_q4km.gguf"
MODEL_REPO="Walusimbi/aletheia-q4km"
MODEL_URL="https://huggingface.co/${MODEL_REPO}/resolve/main/${MODEL_FILE}"
EXPECTED_BYTES=1929902592

mkdir -p "${MODEL_DIR}"
TARGET="${MODEL_DIR}/${MODEL_FILE}"

filesize() {
    stat -c %s "$1" 2>/dev/null || stat -f %z "$1" 2>/dev/null || echo 0
}

# ── Skip if already downloaded and complete ───────────────────
if [ -f "${TARGET}" ]; then
    ACTUAL=$(filesize "${TARGET}")
    if [ "${ACTUAL}" = "${EXPECTED_BYTES}" ]; then
        echo "Model already present: ${TARGET} (complete). Skipping download."
        exit 0
    fi
    echo "Partial download found (${ACTUAL} of ${EXPECTED_BYTES} bytes). Resuming."
fi

# ── Download, resuming a partial file if one exists ───────────
echo "Downloading ${MODEL_FILE} (about 1.8 GB) from Hugging Face."
echo "  ${MODEL_URL}"
echo "If the transfer is interrupted, run this script again and it resumes."
echo ""

curl -L -C - --retry 5 --retry-delay 5 --retry-connrefused \
     --fail --progress-bar \
     -o "${TARGET}" "${MODEL_URL}"

# ── Verify ────────────────────────────────────────────────────
if [ ! -s "${TARGET}" ]; then
    echo "ERROR: the downloaded file is empty." >&2
    rm -f "${TARGET}"
    exit 1
fi

ACTUAL=$(filesize "${TARGET}")
if [ "${ACTUAL}" != "${EXPECTED_BYTES}" ]; then
    echo "ERROR: size mismatch. Expected ${EXPECTED_BYTES} bytes, got ${ACTUAL}." >&2
    echo "       The download is incomplete. Run this script again to resume." >&2
    exit 1
fi

MAGIC=$(head -c 4 "${TARGET}")
if [ "${MAGIC}" != "GGUF" ]; then
    echo "ERROR: ${TARGET} is not a valid GGUF file (first bytes: '${MAGIC}')." >&2
    rm -f "${TARGET}"
    exit 1
fi

echo ""
echo "Done: ${TARGET} ($(du -h "${TARGET}" | cut -f1))"
