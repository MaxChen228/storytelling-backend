#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
DEFAULT_VENV="$REPO_ROOT/.venv"
VENV_PATH="${PODCAST_ENV_PATH:-$DEFAULT_VENV}"
PYTHON_BIN="$VENV_PATH/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "⚠️  找不到虛擬環境：$VENV_PATH" >&2
    echo "請先建立 .venv 並安裝 requirements/base.txt" >&2
    exit 1
fi

exec "$PYTHON_BIN" -m storytelling_cli "$@"
