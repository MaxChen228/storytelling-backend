#!/bin/bash

set -e

# ============================================================================
# 🎙️ Storytelling Podcast - 多書籍工作區管理介面
# ============================================================================

# 判斷終端是否支援顏色
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    PURPLE='\033[0;35m'
    CYAN='\033[0;36m'
    WHITE='\033[1;37m'
    GRAY='\033[0;90m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    PURPLE=''
    CYAN=''
    WHITE=''
    GRAY=''
    NC=''
fi

ICON_SCRIPT="📝"
ICON_AUDIO="🎵"
ICON_SUBTITLE="🧾"
ICON_COMPLETE="✅"
ICON_MISSING="❌"
ICON_WARNING="⚠️"
ICON_BOOK="📚"
ICON_CHAPTER="📖"
ICON_PLAY="▶️"
ICON_SUMMARY="🗒️"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_PATH="$SCRIPT_DIR/podcast_config.yaml"

DEFAULT_VENV="$REPO_ROOT/.venvs/storytelling"
VENV_PATH="${PODCAST_ENV_PATH:-$DEFAULT_VENV}"
PYTHON="$VENV_PATH/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo -e "${YELLOW}${ICON_WARNING} 找不到虛擬環境：$VENV_PATH${NC}"
    echo -e "請執行 ${CYAN}bash ../scripts/bootstrap_venv.sh storytelling${NC} 建立環境，或設定 PODCAST_ENV_PATH"
    exit 1
fi

SUBTITLE_DEVICE_DEFAULT="${PODCAST_SUBTITLE_DEVICE:-cpu}"

# --------------------------------------------------------------------------
# 透過 Python 解析配置檔
# --------------------------------------------------------------------------

python_exports="$("$PYTHON" - "$CONFIG_PATH" <<'PY'
import sys, yaml
from pathlib import Path
from shlex import quote

config_path = Path(sys.argv[1])
with config_path.open('r', encoding='utf-8') as fh:
    cfg = yaml.safe_load(fh)

paths = cfg.get('paths', {})
books_root = Path(paths.get('books_root', './data')).expanduser().resolve()
outputs_root = Path(paths.get('outputs_root', './output')).expanduser().resolve()
transcripts_root = Path(paths.get('transcripts_root', './data/transcripts')).expanduser().resolve()

print(f"BOOKS_ROOT={quote(str(books_root))}")
print(f"OUTPUTS_ROOT={quote(str(outputs_root))}")
print(f"TRANSCRIPTS_ROOT={quote(str(transcripts_root))}")
PY
)"
if [ $? -ne 0 ]; then
    echo -e "${RED}${ICON_MISSING} 無法讀取配置檔：$CONFIG_PATH${NC}"
    exit 1
fi
eval "$python_exports"

CURRENT_BOOK_ID=""
BOOK_DISPLAY_NAME=""
BOOK_DIR=""
SUMMARY_DIR=""
SUMMARY_SUFFIX=""
BOOK_OUTPUT_DIR=""

# --------------------------------------------------------------------------
# 共用工具
# --------------------------------------------------------------------------

eval_python_book_exports() {
    local book_id="$1"
    "$PYTHON" - "$CONFIG_PATH" "$book_id" <<'PY'
import sys, yaml
from pathlib import Path
from shlex import quote

config_path = Path(sys.argv[1])
book_id = sys.argv[2]

with config_path.open('r', encoding='utf-8') as fh:
    cfg = yaml.safe_load(fh)

paths = cfg.get('paths', {})
books_root = Path(paths.get('books_root', './data')).expanduser().resolve()
outputs_root = Path(paths.get('outputs_root', './output')).expanduser().resolve()

books_cfg = cfg.get('books', {})
defaults = books_cfg.get('defaults', {})
overrides = (books_cfg.get('overrides', {}) or {}).get(book_id, {})

merged = dict(defaults)
merged.update(overrides)

summary_subdir = merged.get('summary_subdir', 'summaries')
summary_suffix = merged.get('summary_suffix', '_summary.txt')
display_name = merged.get('book_name') or overrides.get('display_name') or book_id
output_name = overrides.get('output_folder') or merged.get('book_name_override') or display_name

book_dir = books_root / book_id
summary_dir = book_dir / summary_subdir
output_dir = outputs_root / output_name

print(f"CURRENT_BOOK_ID={quote(book_id)}")
print(f"BOOK_DISPLAY_NAME={quote(display_name)}")
print(f"BOOK_DIR={quote(str(book_dir))}")
print(f"SUMMARY_DIR={quote(str(summary_dir))}")
print(f"SUMMARY_SUFFIX={quote(summary_suffix)}")
print(f"BOOK_OUTPUT_DIR={quote(str(output_dir))}")
PY
}

load_book_context() {
    local book_id="$1"
    if [ -z "$book_id" ]; then
        return 1
    fi
    local exports
    exports="$(eval_python_book_exports "$book_id")" || return 1
    eval "$exports"

    if [ ! -d "$BOOK_DIR" ]; then
        echo -e "${RED}${ICON_MISSING} 書籍目錄不存在：$BOOK_DIR${NC}"
        return 1
    fi
    mkdir -p "$SUMMARY_DIR"
    mkdir -p "$BOOK_OUTPUT_DIR"
    return 0
}

list_books() {
    "$PYTHON" - "$CONFIG_PATH" <<'PY'
import sys, yaml
from pathlib import Path

config_path = Path(sys.argv[1])
with config_path.open('r', encoding='utf-8') as fh:
    cfg = yaml.safe_load(fh)

paths = cfg.get('paths', {})
books_root = Path(paths.get('books_root', './data')).expanduser().resolve()

books_cfg = cfg.get('books', {})
defaults = books_cfg.get('defaults', {})
overrides_cfg = books_cfg.get('overrides', {}) or {}

def summarize_book(book_id: str):
    book_dir = books_root / book_id
    if not book_dir.exists() or not book_dir.is_dir():
        return
    overrides = overrides_cfg.get(book_id, {})
    merged = dict(defaults)
    merged.update(overrides)
    pattern = merged.get('file_pattern', 'chapter*.txt')
    text_files = sorted(book_dir.glob(pattern))
    if not text_files:
        return
    summary_dir = book_dir / merged.get('summary_subdir', 'summaries')
    summary_suffix = merged.get('summary_suffix', '_summary.txt')
    summary_count = 0
    if summary_dir.exists():
        summary_count = len(list(summary_dir.glob(f"*{summary_suffix}")))
    display = merged.get('book_name') or overrides.get('display_name') or book_id
    print(f"{book_id}|{display}|{len(text_files)}|{summary_count}")

for child in sorted(p.name for p in books_root.iterdir() if p.is_dir()):
    summarize_book(child)
PY
}

sort_chapters_naturally() {
    printf '%s\n' "$@" | sort -V
}

parse_chapter_range() {
    local input="$1"
    shift
    local available=("$@")
    local sorted=($(sort_chapters_naturally "${available[@]}"))

    if [ "$input" = "all" ] || [ "$input" = "a" ]; then
        printf '%s\n' "${sorted[@]}"
        return 0
    fi

    local selections=()
    IFS=',' read -ra ranges <<< "$input"
    for range in "${ranges[@]}"; do
        range=$(echo "$range" | tr -d ' ')
        if [[ $range =~ ^[0-9]+$ ]]; then
            if [ "$range" -ge 0 ] && [ "$range" -lt "${#sorted[@]}" ]; then
                selections+=("${sorted[$range]}")
            else
                echo "警告：索引 $range 超出範圍 (0-$((${#sorted[@]}-1)))，已跳過" >&2
            fi
        elif [[ $range =~ ^([0-9]+)-([0-9]+)$ ]]; then
            local start="${BASH_REMATCH[1]}"
            local end="${BASH_REMATCH[2]}"
            if [ "$start" -gt "$end" ]; then
                local tmp="$start"
                start="$end"
                end="$tmp"
            fi
            for ((i=start; i<=end; i++)); do
                if [ "$i" -ge 0 ] && [ "$i" -lt "${#sorted[@]}" ]; then
                    selections+=("${sorted[$i]}")
                else
                    echo "警告：索引 $i 超出範圍 (0-$((${#sorted[@]}-1)))，已跳過" >&2
                fi
            done
        else
            local matched=false
            for chapter_name in "${sorted[@]}"; do
                if [ "$chapter_name" = "$range" ]; then
                    selections+=("$chapter_name")
                    matched=true
                    break
                fi
            done
            if [ "$matched" = false ]; then
                echo "錯誤：無效的範圍或章節名稱 '$range'" >&2
                return 1
            fi
        fi
    done

    if [ ${#selections[@]} -eq 0 ]; then
        return 1
    fi

    local unique=()
    local seen=""
    for chapter_name in "${selections[@]}"; do
        if [[ " $seen " != *" $chapter_name "* ]]; then
            unique+=("$chapter_name")
            seen="$seen $chapter_name"
        fi
    done

    printf '%s\n' "${unique[@]}"
}

parallel_execute() {
    local task="$1"
    shift
    local chapters=("$@")
    if [ ${#chapters[@]} -eq 0 ]; then
        echo "錯誤：沒有章節需要處理" >&2
        return 1
    fi

    echo -e "${GRAY}🚀 並行執行 ${#chapters[@]} 個任務...${NC}"

    local tmp_dir
    tmp_dir=$(mktemp -d)
    local pids=()

    for chapter in "${chapters[@]}"; do
        local status_file="$tmp_dir/$chapter.status"
        (
            if $task "$chapter"; then
                echo "success" > "$status_file"
            else
                echo "failed" > "$status_file"
            fi
        ) &
        pids+=($!)
    done

    local pid
    for pid in "${pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done

    local success=0
    local failed=0
    for chapter in "${chapters[@]}"; do
        local status_file="$tmp_dir/$chapter.status"
        if [ -f "$status_file" ]; then
            if [ "$(cat "$status_file")" = "success" ]; then
                ((success++))
            else
                ((failed++))
            fi
        else
            ((failed++))
        fi
    done

    rm -rf "$tmp_dir"

    echo ""
    echo -e "${WHITE}並行完成：${NC} ${GREEN}${success} 成功${NC} / ${RED}${failed} 失敗${NC}"
    [ "$failed" -eq 0 ]
}

# --------------------------------------------------------------------------
# 章節掃描與顯示
# --------------------------------------------------------------------------

scan_chapters() {
    local all=()
    if [ -d "$BOOK_DIR" ]; then
        for file in "$BOOK_DIR"/*.txt; do
            [ -f "$file" ] || continue
            all+=("$(basename "$file" .txt)")
        done
    fi
    if [ -d "$BOOK_OUTPUT_DIR" ]; then
        for dir in "$BOOK_OUTPUT_DIR"/chapter*; do
            [ -d "$dir" ] || continue
            local slug
            slug="$(basename "$dir")"
            local found=false
            for existing in "${all[@]}"; do
                if [ "$existing" = "$slug" ]; then
                    found=true
                    break
                fi
            done
            [ "$found" = false ] && all+=("$slug")
        done
    fi

    if [ ${#all[@]} -eq 0 ]; then
        return 0
    fi

    for chapter in "${all[@]}"; do
        local source=false
        local summary=false
        local script=false
        local audio=false
        local subtitle=false

        [ -f "$BOOK_DIR/$chapter.txt" ] && source=true
        [ -f "$SUMMARY_DIR/${chapter}${SUMMARY_SUFFIX}" ] && summary=true
        [ -f "$BOOK_OUTPUT_DIR/$chapter/podcast_script.txt" ] && script=true
        if [ -f "$BOOK_OUTPUT_DIR/$chapter/podcast.wav" ] || [ -f "$BOOK_OUTPUT_DIR/$chapter/podcast.mp3" ]; then
            audio=true
        fi
        [ -f "$BOOK_OUTPUT_DIR/$chapter/subtitles.srt" ] && subtitle=true

        echo "$chapter|$source|$summary|$script|$audio|$subtitle"
    done | sort -V
}

display_chapters() {
    local entries=($(scan_chapters))
    echo ""
    echo -e "${ICON_BOOK} 書本：${WHITE}${BOOK_DISPLAY_NAME}${NC}"
    echo ""

    if [ ${#entries[@]} -eq 0 ]; then
        echo -e "${YELLOW}${ICON_WARNING} 尚未找到任何章節或源文件${NC}"
        echo ""
        return 1
    fi

    echo "┌──────┬─────────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐"
    printf "│ %-4s │ %-15s │ %-8s │ %-8s │ %-8s │ %-8s │ %-8s │\n" "編號" "章節" "源文件" "摘要" "腳本" "音頻" "字幕"
    echo "├──────┼─────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤"

    local idx=0
    for entry in "${entries[@]}"; do
        IFS='|' read -r chapter has_source has_summary has_script has_audio has_subtitle <<< "$entry"
        local s_source="✗"
        local s_summary="✗"
        local s_script="✗"
        local s_audio="✗"
        local s_subtitle="✗"
        [ "$has_source" = "true" ] && s_source="✓"
        [ "$has_summary" = "true" ] && s_summary="✓"
        [ "$has_script" = "true" ] && s_script="✓"
        [ "$has_audio" = "true" ] && s_audio="✓"
        [ "$has_subtitle" = "true" ] && s_subtitle="✓"
        printf "│ %-4s │ %-15s │    %-5s │    %-5s │    %-5s │    %-5s │    %-5s │\n" \
            "$idx" "$chapter" "$s_source" "$s_summary" "$s_script" "$s_audio" "$s_subtitle"
        ((idx++))
    done
    echo "└──────┴─────────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘"
    echo ""
}

select_chapter_entry() {
    local entries=($(scan_chapters))
    if [ ${#entries[@]} -eq 0 ]; then
        return 1
    fi
    echo -e "${WHITE}請輸入章節索引（0 開始）：${NC}"
    read -p "> " choice
    if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 0 ] || [ "$choice" -ge ${#entries[@]} ]; then
        echo -e "${RED}${ICON_MISSING} 無效的選擇${NC}"
        return 1
    fi
    echo "${entries[$choice]}"
}

# --------------------------------------------------------------------------
# 任務執行
# --------------------------------------------------------------------------

generate_script() {
    local chapter="$1"
    local source_file="$BOOK_DIR/${chapter}.txt"
    if [ ! -f "$source_file" ]; then
        echo -e "${RED}${ICON_MISSING} 找不到源文件：$source_file${NC}"
        return 1
    fi
    echo -e "${GREEN}${ICON_SCRIPT} 生成腳本：${chapter}${NC}"
    if ! "$PYTHON" generate_script.py "$chapter" --config "$CONFIG_PATH" --book-id "$CURRENT_BOOK_ID"; then
        echo -e "${RED}${ICON_MISSING} 腳本生成失敗${NC}"
        return 1
    fi
    echo -e "${GREEN}${ICON_COMPLETE} 腳本完成${NC}"
}

generate_audio() {
    local chapter="$1"
    local script_file="$BOOK_OUTPUT_DIR/$chapter/podcast_script.txt"
    if [ ! -f "$script_file" ]; then
        echo -e "${RED}${ICON_MISSING} 無法生成音頻：${chapter} 尚未有腳本${NC}"
        return 1
    fi
    echo -e "${GREEN}${ICON_AUDIO} 生成音頻：${chapter}${NC}"
    if ! "$PYTHON" generate_audio.py "$BOOK_OUTPUT_DIR/$chapter"; then
        echo -e "${RED}${ICON_MISSING} 音頻生成失敗${NC}"
        return 1
    fi
    echo -e "${GREEN}${ICON_COMPLETE} 音頻完成${NC}"
}

generate_subtitles() {
    local chapter="$1"
    local script_file="$BOOK_OUTPUT_DIR/$chapter/podcast_script.txt"
    local audio_wav="$BOOK_OUTPUT_DIR/$chapter/podcast.wav"
    local audio_mp3="$BOOK_OUTPUT_DIR/$chapter/podcast.mp3"
    if [ ! -f "$script_file" ]; then
        echo -e "${RED}${ICON_MISSING} 無法生成字幕：${chapter} 尚未有腳本${NC}"
        return 1
    fi
    if [ ! -f "$audio_wav" ] && [ ! -f "$audio_mp3" ]; then
        echo -e "${RED}${ICON_MISSING} 無法生成字幕：${chapter} 尚未有音頻${NC}"
        return 1
    fi
    echo -e "${GREEN}${ICON_SUBTITLE} 生成字幕：${chapter}${NC}"
    if ! "$PYTHON" generate_subtitles.py "$BOOK_OUTPUT_DIR/$chapter" --config "$CONFIG_PATH" --device "$SUBTITLE_DEVICE_DEFAULT"; then
        echo -e "${RED}${ICON_MISSING} 字幕生成失敗${NC}"
        return 1
    fi
    echo -e "${GREEN}${ICON_COMPLETE} 字幕完成${NC}"
}

generate_summaries() {
    echo -e "${CYAN}${ICON_SUMMARY} 生成摘要${NC}"
    echo -e "${GRAY}輸入起始章節（1-based，預設 1）：${NC}"
    read -p "> " start
    echo -e "${GRAY}輸入結束章節（1-based，預設至最後一章，留空代表全部）：${NC}"
    read -p "> " end
    echo -e "${GRAY}是否覆寫已存在摘要？ (y/N)：${NC}"
    read -p "> " force_choice

    local args=(--config "$CONFIG_PATH" --book-id "$CURRENT_BOOK_ID")
    if [[ "$start" =~ ^[0-9]+$ ]]; then
        args+=(--start-chapter "$start")
    fi
    if [[ "$end" =~ ^[0-9]+$ ]]; then
        args+=(--end-chapter "$end")
    fi
    if [[ "$force_choice" =~ ^[Yy]$ ]]; then
        args+=(--force)
    fi

    echo ""
    echo -e "${GRAY}命令：${WHITE}$PYTHON preprocess_chapters.py ${args[*]}${NC}"
    "$PYTHON" preprocess_chapters.py "${args[@]}"
}

play_audio_with_subtitles() {
    local chapter="$1"
    local audio=""
    if [ -f "$BOOK_OUTPUT_DIR/$chapter/podcast.wav" ]; then
        audio="$BOOK_OUTPUT_DIR/$chapter/podcast.wav"
    elif [ -f "$BOOK_OUTPUT_DIR/$chapter/podcast.mp3" ]; then
        audio="$BOOK_OUTPUT_DIR/$chapter/podcast.mp3"
    else
        echo -e "${RED}${ICON_MISSING} 找不到音訊檔案：$chapter${NC}"
        return 1
    fi

    local subtitle="$BOOK_OUTPUT_DIR/$chapter/subtitles.srt"
    local player_script="$SCRIPT_DIR/play_with_subtitles.py"

    echo -e "${GREEN}${ICON_PLAY} 播放：${chapter}${NC}"
    if [ -f "$subtitle" ] && [ -f "$player_script" ]; then
        "$PYTHON" "$player_script" "$audio" "$subtitle"
    else
        if command -v afplay >/dev/null 2>&1; then
            afplay "$audio"
        elif command -v ffplay >/dev/null 2>&1; then
            ffplay -nodisp -autoexit "$audio"
        else
            echo -e "${YELLOW}${ICON_WARNING} 找不到播放器，請手動播放：$audio${NC}"
        fi
    fi
}

# --------------------------------------------------------------------------
# 使用者互動
# --------------------------------------------------------------------------

choose_book() {
    local books=()
    while IFS= read -r line; do
        [ -n "$line" ] && books+=("$line")
    done < <(list_books)
    if [ ${#books[@]} -eq 0 ]; then
        echo -e "${RED}${ICON_MISSING} 在 ${BOOKS_ROOT} 下找不到任何書籍章節${NC}"
        exit 1
    fi

    echo ""
    echo -e "${CYAN}可用書籍：${NC}"
    echo ""
    local idx=0
    for entry in "${books[@]}"; do
        IFS='|' read -r book_id display total summary <<< "$entry"
        printf "  ${GRAY}[%s]${NC} %s%s%s  (章節: %s, 已有摘要: %s)\n" \
            "$idx" "${WHITE}" "$display" "${NC}" "$total" "$summary"
        ((idx++))
    done
    echo ""
    echo -e "${WHITE}請輸入書籍索引（或 q 離開）：${NC}"
    read -p "> " choice
    if [ "$choice" = "q" ] || [ "$choice" = "Q" ]; then
        exit 0
    fi
    if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 0 ] || [ "$choice" -ge ${#books[@]} ]; then
        echo -e "${RED}${ICON_MISSING} 無效的選擇${NC}"
        return 1
    fi
    local selected="${books[$choice]}"
    IFS='|' read -r book_id display _ <<< "$selected"
    if load_book_context "$book_id"; then
        CURRENT_BOOK_ID="$book_id"
        BOOK_DISPLAY_NAME="$display"
        echo ""
        echo -e "${GREEN}${ICON_BOOK} 已切換到「${BOOK_DISPLAY_NAME}」${NC}"
        return 0
    else
        return 1
    fi
}

chapter_range_prompt() {
    local purpose="$1"
    local needed_status="$2"   # e.g. script/audio/subtitle
    local optional_status="$3" # optional filter

    local entries=($(scan_chapters))
    local selectable=()
    for entry in "${entries[@]}"; do
        IFS='|' read -r chapter has_source has_summary has_script has_audio has_subtitle <<< "$entry"
        case "$needed_status" in
            source)    [ "$has_source" = "true" ]    || continue ;;
            summary)   [ "$has_summary" = "true" ]   || continue ;;
            nosummary) [ "$has_summary" != "true" ]  || continue ;;
            script)    [ "$has_script" = "true" ]    || continue ;;
            noscript)  [ "$has_script" != "true" ]   || continue ;;
            audio)     [ "$has_audio" = "true" ]     || continue ;;
            noaudio)   [ "$has_audio" != "true" ]    || continue ;;
            subtitle)  [ "$has_subtitle" = "true" ]  || continue ;;
            nosubtitle)[ "$has_subtitle" != "true" ] || continue ;;
            *) ;;
        esac
        if [ -n "$optional_status" ]; then
            case "$optional_status" in
                requires_script) [ "$has_script" = "true" ] || continue ;;
                requires_audio)  [ "$has_audio" = "true" ]  || continue ;;
            esac
        fi
        selectable+=("$chapter")
    done

    if [ ${#selectable[@]} -eq 0 ]; then
        echo -e "${YELLOW}${ICON_WARNING} 沒有符合條件的章節可供 ${purpose}${NC}"
        return 1
    fi

    local sorted=($(sort_chapters_naturally "${selectable[@]}"))
    echo -e "${WHITE}可處理章節（索引從 0 開始）：${NC}" >&2
    local idx=0
    for chapter in "${sorted[@]}"; do
        printf "  ${GRAY}[%s]${NC} %s\n" "$idx" "$chapter" >&2
        ((idx++))
    done
    echo "" >&2
    echo -e "${CYAN}請輸入章節範圍（如 0-5,7-9 或 all，也可直接輸入章節名稱）：${NC}" >&2
    printf "> " >&2
    IFS= read -r range_input || return 1
    if [ -z "$range_input" ]; then
        echo -e "${YELLOW}已取消${NC}"
        return 1
    fi
    local parsed_output
    if ! parsed_output="$(parse_chapter_range "$range_input" "${sorted[@]}" 2>&1)"; then
        [ -n "$parsed_output" ] && echo "$parsed_output" >&2
        return 1
    fi
    local chosen=()
    while IFS= read -r line; do
        [ -n "$line" ] && chosen+=("$line")
    done <<< "$parsed_output"
    if [ ${#chosen[@]} -eq 0 ]; then
        echo -e "${YELLOW}沒有符合的章節${NC}"
        return 1
    fi
    printf '%s\n' "${chosen[@]}"
}

batch_generate_scripts() {
    local output
    if ! output="$(chapter_range_prompt "生成腳本" "source")"; then
        return 1
    fi
    local chapters=()
    while IFS= read -r line; do
        [ -n "$line" ] && chapters+=("$line")
    done <<< "$output"
    if [ ${#chapters[@]} -eq 0 ]; then
        echo -e "${YELLOW}沒有符合的章節${NC}"
        return 1
    fi
    echo ""
    echo -e "${WHITE}準備為以下章節生成腳本：${NC}"
    printf "  %s\n" "${chapters[@]}"
    echo ""
    local entry
    for entry in "${chapters[@]}"; do
        generate_script "$entry"
    done
}

batch_generate_audio() {
    local output
    if ! output="$(chapter_range_prompt "生成音頻" "script")"; then
        return 1
    fi
    local chapters=()
    while IFS= read -r line; do
        [ -n "$line" ] && chapters+=("$line")
    done <<< "$output"
    if [ ${#chapters[@]} -eq 0 ]; then
        echo -e "${YELLOW}沒有符合的章節${NC}"
        return 1
    fi
    echo ""
    echo -e "${WHITE}準備為以下章節生成音頻：${NC}"
    printf "  %s\n" "${chapters[@]}"
    echo ""
    parallel_execute generate_audio "${chapters[@]}"
}

batch_generate_subtitles() {
    local output
    if ! output="$(chapter_range_prompt "生成字幕" "audio" "requires_script")"; then
        return 1
    fi
    local chapters=()
    while IFS= read -r line; do
        [ -n "$line" ] && chapters+=("$line")
    done <<< "$output"
    if [ ${#chapters[@]} -eq 0 ]; then
        echo -e "${YELLOW}沒有符合的章節${NC}"
        return 1
    fi
    echo ""
    echo -e "${WHITE}準備為以下章節生成字幕：${NC}"
    printf "  %s\n" "${chapters[@]}"
    echo ""
    local chapter
    for chapter in "${chapters[@]}"; do
        generate_subtitles "$chapter" || true
    done
}

batch_play_audio() {
    local entry
    entry="$(select_chapter_entry)" || return 1
    IFS='|' read -r chapter _ _ _ has_audio has_subtitle <<< "$entry"
    if [ "$has_audio" != "true" ]; then
        echo -e "${RED}${ICON_MISSING} 此章節尚未生成音頻${NC}"
        return 1
    fi
    play_audio_with_subtitles "$chapter"
}

main_menu() {
    while true; do
        display_chapters
        echo -e "${CYAN}操作選單：${NC}"
        echo "  1) 生成腳本"
        echo "  2) 生成音頻"
        echo "  3) 生成字幕"
        echo "  4) 生成摘要"
        echo "  5) 播放音頻"
        echo "  6) 切換書籍"
        echo "  r) 重新整理"
        echo "  q) 離開"
        echo ""
        read -p "> " choice
        case "$choice" in
            1) batch_generate_scripts ;;
            2) batch_generate_audio ;;
            3) batch_generate_subtitles ;;
            4) generate_summaries ;;
            5) batch_play_audio ;;
            6) if choose_book; then continue; else continue; fi ;;
            r|R) continue ;;
            q|Q) exit 0 ;;
            *) echo -e "${YELLOW}${ICON_WARNING} 無效選項${NC}" ;;
        esac
    done
}

# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------

while ! choose_book; do
    :
done

main_menu
