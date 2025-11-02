#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
DEFAULT_VENV="$REPO_ROOT/.venv"
VENV_PATH="${PODCAST_ENV_PATH:-$DEFAULT_VENV}"
PYTHON_BIN="$VENV_PATH/bin/python"
OUTPUT_DIR="$REPO_ROOT/output"
SYNC_BUCKET="${STORYTELLING_SYNC_BUCKET:-${GCS_SYNC_BUCKET:-}}"
DEFAULT_SYNC_EXCLUDE='(^|/)\\.DS_Store$|(^|/)\\.gitignore$|(^|/)\\.env$|(^|/)\\.pytest_cache($|/.*)|.*\\.wav$'
SYNC_EXCLUDE_REGEX="${STORYTELLING_SYNC_EXCLUDE_REGEX:-$DEFAULT_SYNC_EXCLUDE}"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "⚠️  找不到虛擬環境：$VENV_PATH" >&2
    echo "請先建立 .venv 並安裝 requirements/base.txt" >&2
    exit 1
fi

if [ "$#" -gt 0 ] && [ "${1}" = "delete" ]; then
    shift
    exec "$PYTHON_BIN" -m storytelling_cli delete "$@"
fi

set +e
"$PYTHON_BIN" -m storytelling_cli "$@"
CLI_EXIT=$?
set -e

if [ "$CLI_EXIT" -eq 0 ] && [ -n "$SYNC_BUCKET" ]; then
    if ! command -v gsutil >/dev/null 2>&1; then
        echo "⚠️  找不到 gsutil，略過同步。" >&2
    elif [ ! -d "$OUTPUT_DIR" ]; then
        echo "⚠️  找不到輸出目錄：$OUTPUT_DIR" >&2
    else
        echo "☁️  正在同步 $OUTPUT_DIR → $SYNC_BUCKET（排除 WAV 與隱藏檔）"
        if ! gsutil -m rsync -d -r -x "$SYNC_EXCLUDE_REGEX" "$OUTPUT_DIR" "$SYNC_BUCKET"; then
            echo "⚠️  gsutil rsync 失敗，請稍後重試。" >&2
        else
            echo "✅ 同步完成。"
        fi
    fi
fi

exit "$CLI_EXIT"
