#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"

DOTENV_PATH="$REPO_ROOT/.env"
if [ -z "${STORYTELLING_SKIP_DOTENV:-}" ] && [ -f "$DOTENV_PATH" ]; then
    # 將 .env 中的設定載入環境，供 CLI 與子程序使用
    # shellcheck disable=SC1090
    set -a
    source "$DOTENV_PATH"
    set +a
fi

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

run_storytelling_cli() {
    set +e
    "$PYTHON_BIN" -m storytelling_cli "$@"
    local exit_code=$?
    set -e

    if [ "$exit_code" -eq 0 ] && [ -n "$SYNC_BUCKET" ]; then
        if ! command -v gsutil >/dev/null 2>&1; then
            echo "⚠️  找不到 gsutil，略過同步。" >&2
        elif [ ! -d "$OUTPUT_DIR" ]; then
            echo "⚠️  找不到輸出目錄：$OUTPUT_DIR" >&2
        else
            echo "☁️  正在同步 ${OUTPUT_DIR} → ${SYNC_BUCKET} (排除 WAV 與隱藏檔)"
            if ! gsutil -m rsync -d -r -x "$SYNC_EXCLUDE_REGEX" "$OUTPUT_DIR" "$SYNC_BUCKET"; then
                echo "⚠️  gsutil rsync 失敗，請稍後重試。" >&2
            else
                echo "✅ 同步完成。"
            fi
        fi
    fi
    return "$exit_code"
}

manual_sync() {
    if [ -z "$SYNC_BUCKET" ]; then
        echo "⚠️  尚未設定 STORYTELLING_SYNC_BUCKET，無法同步。" >&2
        return 1
    fi
    if ! command -v gsutil >/dev/null 2>&1; then
        echo "⚠️  找不到 gsutil，請先安裝 Google Cloud SDK。" >&2
        return 1
    fi
    if [ ! -d "$OUTPUT_DIR" ]; then
        echo "⚠️  找不到輸出目錄：$OUTPUT_DIR" >&2
        return 1
    fi
    echo "☁️  開始同步 ${OUTPUT_DIR} → ${SYNC_BUCKET} (排除 WAV 與隱藏檔)"
    gsutil -m rsync -d -r -x "$SYNC_EXCLUDE_REGEX" "$OUTPUT_DIR" "$SYNC_BUCKET"
}

list_books() {
    "$PYTHON_BIN" - <<'PY'
from storytelling_cli.__main__ import StorytellingCLI

cli = StorytellingCLI()
books = cli.list_books()
if not books:
    print("⚠️  未找到任何書籍。")
else:
    print("可用書籍：")
    for idx, book in enumerate(books):
        print(f"  [{idx}] {book['display_name']} (ID: {book['book_id']}, 章節: {book['total_chapters']}, 摘要: {book['summary_count']})")
PY
}

rename_book() {
    "$PYTHON_BIN" "$REPO_ROOT/scripts/rename_book.py"
}

manage_books() {
    echo "📚 目前書籍列表："
    list_books
    echo
    printf "需要進行改名嗎？(y/N)："
    read -r answer
    case "$answer" in
        y|Y)
            rename_book
            echo
            echo "📚 更新後的書籍列表："
            list_books
            ;;
        *)
            echo "ℹ️  未進行改名。"
            ;;
    esac
}

if [ "$#" -gt 0 ]; then
    if [ "${1}" = "delete" ]; then
        shift
        exec "$PYTHON_BIN" -m storytelling_cli delete "$@"
    else
        run_storytelling_cli "$@"
        exit "$?"
    fi
fi

while true; do
    echo
    echo "====== Storytelling 工具 ======"
    echo "1) 啟動互動式 CLI"
    echo "2) 查看 / 改名書籍"
    echo "3) 手動同步 output → GCS"
    echo "4) 離開"
    printf "請選擇："
    read -r choice
    echo
    case "$choice" in
        1)
            run_storytelling_cli
            ;;
        2)
            manage_books
            ;;
        3)
            manual_sync
            ;;
        4|q|Q)
            echo "再見！"
            exit 0
            ;;
        *)
            echo "⚠️  無效選項，請重新輸入。"
            ;;
    esac
done
