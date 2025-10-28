#!/bin/bash
set -euo pipefail

MIN_PY_VERSION="3.9"
TARGET="${1:-}"

usage() {
  echo "Usage: $(basename "$0") <storytelling|podcast>"
  echo "可選環境：storytelling（單聲線 CLI）、podcast（多來源 CLI）"
}

if [[ -z "$TARGET" ]]; then
  usage
  exit 1
fi

case "$TARGET" in
  storytelling|podcast)
    ;;
  *)
    echo "[bootstrap] 未知環境：$TARGET" >&2
    usage
    exit 1
    ;;
esac

if ! command -v python3 >/dev/null 2>&1; then
  echo "[bootstrap] 找不到 python3，請先安裝 Python $MIN_PY_VERSION 以上版本" >&2
  exit 1
fi

PY_CMD="${PYTHON_BIN:-python3}"
if ! command -v "$PY_CMD" >/dev/null 2>&1; then
  echo "[bootstrap] 找不到指定的 PYTHON_BIN=$PY_CMD" >&2
  exit 1
fi

PY_VERSION=$("$PY_CMD" - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)

version_ge() {
  python3 - "$1" "$2" <<'PY'
import sys
cur = tuple(map(int, sys.argv[1].split('.')))
req = tuple(map(int, sys.argv[2].split('.')))
print(int(cur >= req))
PY
}

if [[ $(version_ge "$PY_VERSION" "$MIN_PY_VERSION") -ne 1 ]]; then
  echo "[bootstrap] Python 版本過低 ($PY_VERSION)，需要 >= $MIN_PY_VERSION" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_ROOT="$ROOT_DIR/.venvs"
VENV_PATH="$VENV_ROOT/$TARGET"

mkdir -p "$VENV_ROOT"

if [[ ! -d "$VENV_PATH" ]]; then
  echo "[bootstrap] 建立虛擬環境：$VENV_PATH"
  "$PY_CMD" -m venv "$VENV_PATH"
else
  echo "[bootstrap] 虛擬環境已存在：$VENV_PATH"
fi

# shellcheck disable=SC1090
source "$VENV_PATH/bin/activate"

python -m pip install --upgrade pip >/dev/null
pip install -r "$ROOT_DIR/requirements/base.txt"

deactivate >/dev/null

echo "[bootstrap] ✅ $TARGET 環境就緒：$VENV_PATH"
echo "[bootstrap] 提示：source $VENV_PATH/bin/activate"
