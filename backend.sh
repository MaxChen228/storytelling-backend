#!/bin/bash
# 快速啟動 FastAPI 後端並顯示可分享的區網位址

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

HOST="${BACKEND_HOST:-0.0.0.0}"
PORT="${BACKEND_PORT:-8000}"

# 嘗試釋放目標埠
if command -v lsof >/dev/null 2>&1; then
    PIDS=$(lsof -ti tcp:"$PORT" || true)
    if [ -n "$PIDS" ]; then
        echo "🛑  偵測到埠 $PORT 已被使用，嘗試結束相關程序..."
        echo "$PIDS" | xargs kill 2>/dev/null || true
        sleep 1
    fi
fi

LOCAL_IP="$($PYTHON_BIN - <<'PY'
import socket

def get_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 連到外部 DNS，不真的送出封包，只為了取得路由出的 IP
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        sock.close()

print(get_ip())
PY
)"

ACCESS_URL="http://${LOCAL_IP}:${PORT}"

printf "\n📡  區網位址：%s\n" "$ACCESS_URL"
printf "🚀  啟動 FastAPI：uvicorn server.app.main:app --host %s --port %s --reload\n\n" "$HOST" "$PORT"

cd "$REPO_ROOT"

exec "$PYTHON_BIN" -m uvicorn server.app.main:app --host "$HOST" --port "$PORT" --reload
