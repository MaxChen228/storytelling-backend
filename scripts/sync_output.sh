#!/bin/bash
set -euo pipefail

# Synchronise the local output/ directory to the configured GCS bucket.
# Usage: ./scripts/sync_output.sh [bucket-name]

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${PROJECT_ROOT}/output"

DEFAULT_BUCKET="storytelling-output"
BUCKET="${1:-${SYNC_OUTPUT_BUCKET:-$DEFAULT_BUCKET}}"

if ! command -v gsutil >/dev/null 2>&1; then
  echo "❌ gsutil not found. Please install Google Cloud SDK first." >&2
  exit 1
fi

if [ ! -d "${OUTPUT_DIR}" ]; then
  echo "⚠️  Nothing to sync: ${OUTPUT_DIR} does not exist." >&2
  exit 0
fi

EXCLUDE_REGEX="${SYNC_OUTPUT_EXCLUDE:-'.*\\.DS_Store$|^.*/sessions/.*|.*\\.wav$|.*\\.textgrid$'}"
DEST="gs://${BUCKET}/output"
echo "🚀 Syncing ${OUTPUT_DIR}/ → ${DEST}"
echo "🛠  Exclude pattern: ${EXCLUDE_REGEX}"
gsutil -m rsync -r -x "${EXCLUDE_REGEX}" "${OUTPUT_DIR}" "${DEST}"
echo "✅ Sync completed."
