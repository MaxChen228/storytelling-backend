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
            echo "☁️  正在同步 $OUTPUT_DIR → $SYNC_BUCKET（排除 WAV 與隱藏檔）"
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
    echo "☁️  開始同步 $OUTPUT_DIR → $SYNC_BUCKET（排除 WAV 與隱藏檔）"
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
    echo "2) 書籍改名（rename_book）"
    echo "3) 手動同步 output → GCS"
    echo "4) 列出可用書籍"
    echo "5) 離開"
    printf "請選擇："
    read -r choice
    echo
    case "$choice" in
        1)
            run_storytelling_cli
            ;;
        2)
            rename_book
            ;;
        3)
            manual_sync
            ;;
        4)
            list_books
            ;;
        5|q|Q)
            echo "再見！"
            exit 0
            ;;
        *)
            echo "⚠️  無效選項，請重新輸入。"
            ;;
    esac
done
