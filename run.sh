#!/bin/bash

set -e  # 遇到錯誤立即退出

# ============================================================================
# 🎙️ Storytelling Podcast - 直觀互動式管理介面
# ============================================================================

# 檢測是否為 TTY（終端），如果不是則禁用顏色
if [ -t 1 ]; then
    # 是 TTY，啟用顏色
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
    # 不是 TTY（被重定向或捕獲），禁用顏色
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

# 圖標定義
ICON_SCRIPT="📝"
ICON_AUDIO="🎵"
ICON_COMPLETE="✅"
ICON_MISSING="❌"
ICON_WARNING="⚠️"
ICON_BOOK="📚"
ICON_CHAPTER="📖"
ICON_SUBTITLE="🧾"
ICON_PLAY="▶️"

# Foundation 目錄
FOUNDATION_DIR="output/foundation"
DATA_DIR="data/foundation"

# Python 虛擬環境（預設使用 monorepo/.venvs/storytelling，可透過 PODCAST_ENV_PATH 覆寫）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_VENV="$REPO_ROOT/.venvs/storytelling"
VENV_PATH="${PODCAST_ENV_PATH:-$DEFAULT_VENV}"
PYTHON="$VENV_PATH/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo -e "${YELLOW}${ICON_WARNING} 找不到虛擬環境：$VENV_PATH${NC}"
    echo -e "請執行 ${CYAN}bash ../scripts/bootstrap_venv.sh storytelling${NC} 或設置 PODCAST_ENV_PATH 指向既有環境"
    exit 1
fi

SUBTITLE_DEVICE_DEFAULT="${PODCAST_SUBTITLE_DEVICE:-cpu}"

# ============================================================================
# 工具函數
# ============================================================================

# 自然排序章節（chapter0, chapter1, chapter2, ..., chapter10, ...）
sort_chapters_naturally() {
    # 使用 sort -V (version sort) 进行自然排序
    printf '%s\n' "$@" | sort -V
}

# 解析章节范围输入（支持 "1-5,7-9" 或 "all"）
parse_chapter_range() {
    local input="$1"
    shift
    local available_chapters=("$@")

    # 对可用章节进行自然排序
    local sorted_chapters=($(sort_chapters_naturally "${available_chapters[@]}"))

    # 如果输入是 "all" 或 "a"，返回所有章节
    if [ "$input" = "all" ] || [ "$input" = "a" ]; then
        printf '%s\n' "${sorted_chapters[@]}"
        return 0
    fi

    # 解析范围
    local selected_indices=()
    IFS=',' read -ra ranges <<< "$input"

    for range in "${ranges[@]}"; do
        # 去除空格
        range=$(echo "$range" | tr -d ' ')

        if [[ $range =~ ^[0-9]+$ ]]; then
            # 单个数字
            selected_indices+=("$range")
        elif [[ $range =~ ^([0-9]+)-([0-9]+)$ ]]; then
            # 范围 (如 "1-5")
            local start="${BASH_REMATCH[1]}"
            local end="${BASH_REMATCH[2]}"
            for ((i=start; i<=end; i++)); do
                selected_indices+=("$i")
            done
        else
            echo "错误：无效的范围格式 '$range'" >&2
            return 1
        fi
    done

    # 去重并排序
    local unique_indices=($(printf '%s\n' "${selected_indices[@]}" | sort -n | uniq))

    # 将索引转换为章节名（从 0 开始）
    local selected_chapters=()
    for idx in "${unique_indices[@]}"; do
        if [ "$idx" -ge 0 ] && [ "$idx" -lt "${#sorted_chapters[@]}" ]; then
            selected_chapters+=("${sorted_chapters[$idx]}")
        else
            echo "警告：索引 $idx 超出范围 (0-$((${#sorted_chapters[@]}-1)))，已跳过" >&2
        fi
    done

    printf '%s\n' "${selected_chapters[@]}"
    return 0
}

# 并行执行任务
parallel_execute() {
    local task_function="$1"
    shift
    local chapters=("$@")

    if [ ${#chapters[@]} -eq 0 ]; then
        echo "错误：没有章节需要处理" >&2
        return 1
    fi

    echo -e "${GRAY}🚀 并行执行 ${#chapters[@]} 个任务...${NC}"
    echo ""

    local pids=()
    local tmp_dir=$(mktemp -d)

    # 启动所有后台任务
    for chapter in "${chapters[@]}"; do
        local status_file="$tmp_dir/$chapter.status"
        (
            if $task_function "$chapter"; then
                echo "success" > "$status_file"
            else
                echo "failed" > "$status_file"
            fi
        ) &
        pids+=($!)
    done

    # 等待所有任务完成
    for pid in "${pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done

    # 收集结果
    local success=0
    local failed=0
    for chapter in "${chapters[@]}"; do
        local status_file="$tmp_dir/$chapter.status"
        if [ -f "$status_file" ]; then
            local status=$(cat "$status_file")
            if [ "$status" = "success" ]; then
                ((success++))
            else
                ((failed++))
            fi
        else
            ((failed++))
        fi
    done

    # 清理临时文件
    rm -rf "$tmp_dir"

    echo ""
    echo -e "${WHITE}并行执行完成！${NC}"
    echo -e "  成功: ${GREEN}$success${NC}"
    echo -e "  失败: ${RED}$failed${NC}"

    if [ "$failed" -gt 0 ]; then
        return "$failed"
    fi

    return 0
}

# 顯示標題
show_header() {
    if [ -t 1 ]; then
        clear
    fi
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║         🎙️  Storytelling Podcast - Foundation 專案管理               ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# 掃描章節狀態（合併 data/ 和 output/ 目錄）
scan_chapters() {
    local all_chapters=()

    # 第一步：掃描源文件（data/foundation/*.txt）
    if [ -d "$DATA_DIR" ]; then
        for file in "$DATA_DIR"/*.txt; do
            [ -f "$file" ] || continue
            local chapter_name=$(basename "$file" .txt)
            all_chapters+=("$chapter_name")
        done
    fi

    # 第二步：掃描輸出目錄（output/foundation/chapter*）
    if [ -d "$FOUNDATION_DIR" ]; then
        for dir in "$FOUNDATION_DIR"/chapter*; do
            [ -d "$dir" ] || continue
            local chapter_name=$(basename "$dir")
            # 檢查是否已在列表中（去重）
            local found=false
            for existing in "${all_chapters[@]}"; do
                if [ "$existing" = "$chapter_name" ]; then
                    found=true
                    break
                fi
            done
            [ "$found" = false ] && all_chapters+=("$chapter_name")
        done
    fi

    # 如果沒有找到任何章節
    if [ ${#all_chapters[@]} -eq 0 ]; then
        return 0
    fi

    # 第三步：對每個章節檢查完整狀態並輸出
    for chapter in "${all_chapters[@]}"; do
        local has_source=false
        local has_script=false
        local has_audio=false
        local has_subtitle=false

        # 檢查源文件
        [ -f "$DATA_DIR/$chapter.txt" ] && has_source=true

        # 檢查腳本
        [ -f "$FOUNDATION_DIR/$chapter/podcast_script.txt" ] && has_script=true

        # 檢查音頻
        if [ -f "$FOUNDATION_DIR/$chapter/podcast.wav" ] || [ -f "$FOUNDATION_DIR/$chapter/podcast.mp3" ]; then
            has_audio=true
        fi

        if [ -f "$FOUNDATION_DIR/$chapter/subtitles.srt" ]; then
            has_subtitle=true
        fi

        # 輸出格式：章節名|源文件|腳本|音頻|字幕
        echo "$chapter|$has_source|$has_script|$has_audio|$has_subtitle"
    done | sort -V  # 使用版本排序（自然排序）以正確處理 chapter1, chapter2, ..., chapter10
}

# 顯示章節列表（簡潔表格版）
display_chapters() {
    echo "${ICON_BOOK} 書本：Foundation"
    echo ""

    local chapters=($(scan_chapters))

    if [ ${#chapters[@]} -eq 0 ]; then
        echo "${ICON_WARNING} 尚未找到任何章節或源文件"
        echo ""
        return 1
    fi

    # 表格邊框（添加源文件欄位）
    echo "┌──────┬─────────────────┬──────────┬──────────┬──────────┬──────────┐"
    printf "│ %-4s │ %-15s │ %-8s │ %-8s │ %-8s │ %-8s │\n" "編號" "章節" "源文件" "腳本" "音頻" "字幕"
    echo "├──────┼─────────────────┼──────────┼──────────┼──────────┼──────────┤"

    # 顯示每個章節
    local index=0
    for entry in "${chapters[@]}"; do
        IFS='|' read -r chapter has_source has_script has_audio has_subtitle <<< "$entry"

        # 使用簡單的 ✓ 和 ✗ 符號
        local source_status="✗"
        local script_status="✗"
        local audio_status="✗"
        local subtitle_status="✗"

        [ "$has_source" = "true" ] && source_status="✓"
        [ "$has_script" = "true" ] && script_status="✓"
        [ "$has_audio" = "true" ] && audio_status="✓"
        [ "$has_subtitle" = "true" ] && subtitle_status="✓"

        printf "│ %-4s │ %-15s │    %-5s │    %-5s │    %-5s │    %-5s │\n" \
            "$index" \
            "$chapter" \
            "$source_status" \
            "$script_status" \
            "$audio_status" \
            "$subtitle_status"

        index=$((index + 1))
    done

    echo "└──────┴─────────────────┴──────────┴──────────┴──────────┴──────────┘"
    echo ""
}

# 選擇章節
select_chapter() {
    local chapters=($(scan_chapters))

    if [ ${#chapters[@]} -eq 0 ]; then
        return 1
    fi

    # 使用 >&2 將提示輸出到 stderr，避免污染返回值
    echo -e "${WHITE}請選擇章節編號（0 開始）：${NC}" >&2
    read -p "> " choice

    if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 0 ] || [ "$choice" -ge ${#chapters[@]} ]; then
        echo -e "${RED}${ICON_MISSING} 無效的選擇${NC}" >&2
        return 1
    fi

    local entry="${chapters[$choice]}"
    IFS='|' read -r chapter has_source has_script has_audio has_subtitle <<< "$entry"

    # 只有這一行輸出到 stdout，作為返回值（新格式：4 個字段）
    echo "$chapter|$has_source|$has_script|$has_audio|$has_subtitle"
}

# 生成腳本
generate_script() {
    local chapter=$1

    echo ""
    echo -e "${GREEN}${ICON_SCRIPT} 生成腳本：${chapter}${NC}"

    # 檢查源文件是否存在
    local source_file="$DATA_DIR/${chapter}.txt"
    if [ ! -f "$source_file" ]; then
        echo -e "${RED}${ICON_MISSING} 源文件不存在: $source_file${NC}"
        echo -e "${YELLOW}${ICON_WARNING} 請確保在 $DATA_DIR/ 目錄下有 ${chapter}.txt 文件${NC}"
        return 1
    fi

    # 調用腳本生成程式
    if ! "$PYTHON" generate_script.py "$chapter"; then
        echo -e "${RED}${ICON_MISSING} 腳本生成失敗${NC}"
        return 1
    fi

    echo -e "${GREEN}${ICON_COMPLETE} 腳本任務完成${NC}"
}

# 生成音頻
generate_audio() {
    local chapter=$1
    local has_script=$2

    # 檢查是否有腳本
    if [ "$has_script" != "true" ]; then
        echo ""
        echo -e "${RED}${ICON_MISSING} 無法生成音頻：${chapter} 尚未生成腳本${NC}"
        echo -e "${YELLOW}${ICON_WARNING} 請先執行「生成腳本」選項${NC}"
        return 1
    fi

    echo ""
    echo -e "${GREEN}${ICON_AUDIO} 生成音頻：${chapter}${NC}"

    # 調用音頻生成程式
    if ! "$PYTHON" generate_audio.py "$FOUNDATION_DIR/$chapter"; then
        echo -e "${RED}${ICON_MISSING} 音頻生成失敗${NC}"
        return 1
    fi

    echo -e "${GREEN}${ICON_COMPLETE} 音頻任務完成${NC}"
}

# 生成字幕
generate_subtitles() {
    local chapter=$1
    local has_script=$2
    local has_audio=$3

    if [ "$has_script" != "true" ]; then
        echo ""
        echo -e "${RED}${ICON_MISSING} 無法生成字幕：${chapter} 尚未生成腳本${NC}"
        echo -e "${YELLOW}${ICON_WARNING} 請先執行「生成腳本」選項${NC}"
        return 1
    fi

    if [ "$has_audio" != "true" ]; then
        echo ""
        echo -e "${RED}${ICON_MISSING} 無法生成字幕：${chapter} 尚未生成音頻${NC}"
        echo -e "${YELLOW}${ICON_WARNING} 請先執行「生成音頻」選項${NC}"
        return 1
    fi

    local chapter_dir="$FOUNDATION_DIR/$chapter"

    echo ""
    echo -e "${GREEN}${ICON_SUBTITLE} 生成字幕：${chapter}${NC}"

    local device_flag=("--device" "$SUBTITLE_DEVICE_DEFAULT")
    if ! "$PYTHON" generate_subtitles.py "$chapter_dir" "${device_flag[@]}"; then
        echo -e "${RED}${ICON_MISSING} 字幕生成失敗${NC}"
        return 1
    fi

    echo -e "${GREEN}${ICON_COMPLETE} 字幕任務完成${NC}"
}

# 播放音訊並同步字幕
play_audio_with_subtitles() {
    local chapter=$1
    local has_audio=$2
    local has_subtitle=$3

    if [ "$has_audio" != "true" ]; then
        echo ""
        echo -e "${RED}${ICON_MISSING} 無法播放：${chapter} 尚未生成音頻${NC}"
        return 1
    fi

    local chapter_dir="$FOUNDATION_DIR/$chapter"
    local audio_file=""
    if [ -f "$chapter_dir/podcast.wav" ]; then
        audio_file="$chapter_dir/podcast.wav"
    elif [ -f "$chapter_dir/podcast.mp3" ]; then
        audio_file="$chapter_dir/podcast.mp3"
    else
        echo ""
        echo -e "${RED}${ICON_MISSING} 找不到音訊檔案：$chapter_dir/podcast.(wav|mp3)${NC}"
        return 1
    fi

    local subtitle_file="$chapter_dir/subtitles.srt"
    if [ "$has_subtitle" = "true" ] && [ ! -f "$subtitle_file" ]; then
        echo ""
        echo -e "${YELLOW}${ICON_WARNING} 字幕檔案缺失：$subtitle_file${NC}"
    fi

    local player_script="$SCRIPT_DIR/play_with_subtitles.py"
    if [ ! -f "$player_script" ]; then
        echo ""
        echo -e "${RED}${ICON_MISSING} 找不到播放腳本：$player_script${NC}"
        echo -e "${YELLOW}${ICON_WARNING} 請確認已將 play_with_subtitles.py 放在 storytelling_cli 目錄下${NC}"
        return 1
    fi

    echo ""
    echo -e "${GREEN}${ICON_PLAY} 播放中：${chapter}${NC}"
    echo -e "  音訊：$audio_file"
    if [ -f "$subtitle_file" ]; then
        echo -e "  字幕：$subtitle_file"
        "$PYTHON" "$player_script" "$audio_file" "$subtitle_file"
    else
        echo -e "  字幕：未找到，僅播放音訊"
        if command -v afplay >/dev/null 2>&1; then
            afplay "$audio_file"
        elif command -v ffplay >/dev/null 2>&1; then
            ffplay -nodisp -autoexit "$audio_file"
        else
            echo -e "${YELLOW}${ICON_WARNING} 未偵測到可用播放器，請手動播放：$audio_file${NC}"
        fi
    fi
}

# 批次生成腳本
batch_generate_scripts() {
    echo ""
    echo -e "${GREEN}📚 生成腳本（可輸入單章或範圍）${NC}"
    echo -e "${GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    # 掃描 data/foundation/ 目錄
    local source_files=()
    for file in "$DATA_DIR"/*.txt; do
        [ -f "$file" ] || continue
        local basename=$(basename "$file" .txt)
        source_files+=("$basename")
    done

    if [ ${#source_files[@]} -eq 0 ]; then
        echo -e "${YELLOW}${ICON_WARNING} 在 $DATA_DIR/ 目錄下沒有找到任何 .txt 文件${NC}"
        return 1
    fi

    # 自然排序
    local sorted_files=($(sort_chapters_naturally "${source_files[@]}"))

    echo -e "${WHITE}找到 ${#sorted_files[@]} 個源文件：${NC}"
    local idx=0
    for file in "${sorted_files[@]}"; do
        echo -e "  ${GRAY}[$idx]${NC} ${ICON_CHAPTER} $file"
        ((idx++))
    done
    echo ""

    echo -e "${CYAN}請輸入要生成的章節範圍（索引從 0 開始）：${NC}"
    echo -e "${GRAY}  • 範例: ${WHITE}0-5${GRAY} (生成前 6 章)${NC}"
    echo -e "${GRAY}  • 範例: ${WHITE}0,2,4${GRAY} (生成第 0, 2, 4 章)${NC}"
    echo -e "${GRAY}  • 範例: ${WHITE}1-3,7-9${GRAY} (生成第 1-3 和 7-9 章)${NC}"
    echo -e "${GRAY}  • 輸入 ${WHITE}all${GRAY} 生成所有章節${NC}"
    echo ""
    read -p "範圍: " range_input

    if [ -z "$range_input" ]; then
        echo -e "${YELLOW}已取消${NC}"
        return 0
    fi

    # 解析范围
    local selected_chapters=($(parse_chapter_range "$range_input" "${sorted_files[@]}"))
    if [ $? -ne 0 ] || [ ${#selected_chapters[@]} -eq 0 ]; then
        echo -e "${RED}${ICON_MISSING} 無效的範圍輸入${NC}"
        return 1
    fi

    echo ""
    echo -e "${WHITE}將生成以下 ${#selected_chapters[@]} 個章節：${NC}"
    for chapter in "${selected_chapters[@]}"; do
        echo -e "  ${ICON_CHAPTER} $chapter"
    done
    echo ""

    read -p "是否繼續？ (y/n): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo -e "${YELLOW}已取消${NC}"
        return 0
    fi

    # 並行執行
    local status=0
    if ! parallel_execute generate_script "${selected_chapters[@]}"; then
        status=$?
        echo ""
        echo -e "${YELLOW}${ICON_WARNING} 部分章節處理失敗，請檢查以上訊息${NC}"
    fi

    return $status
}

# 批次生成音頻
batch_generate_audio() {
    echo ""
    echo -e "${GREEN}🎵 生成音頻（可輸入單章或範圍）${NC}"
    echo -e "${GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    local chapters=($(scan_chapters))
    local available=()

    # 找出有腳本但沒有音頻的章節
    for entry in "${chapters[@]}"; do
        IFS='|' read -r chapter has_source has_script has_audio has_subtitle <<< "$entry"

        if [ "$has_script" = "true" ] && [ "$has_audio" != "true" ]; then
            available+=("$chapter")
        fi
    done

    if [ ${#available[@]} -eq 0 ]; then
        echo -e "${YELLOW}${ICON_WARNING} 沒有需要生成音頻的章節${NC}"
        echo -e "${GRAY}（所有有腳本的章節都已有音頻）${NC}"
        return 0
    fi

    # 自然排序
    local sorted_available=($(sort_chapters_naturally "${available[@]}"))

    echo -e "${WHITE}找到 ${#sorted_available[@]} 個可生成音頻的章節：${NC}"
    local idx=0
    for chapter in "${sorted_available[@]}"; do
        echo -e "  ${GRAY}[$idx]${NC} ${ICON_CHAPTER} $chapter"
        ((idx++))
    done
    echo ""

    echo -e "${CYAN}請輸入要生成的章節範圍（索引從 0 開始）：${NC}"
    echo -e "${GRAY}  • 範例: ${WHITE}0-5${GRAY} (生成前 6 章)${NC}"
    echo -e "${GRAY}  • 範例: ${WHITE}0,2,4${GRAY} (生成第 0, 2, 4 章)${NC}"
    echo -e "${GRAY}  • 範例: ${WHITE}1-3,7-9${GRAY} (生成第 1-3 和 7-9 章)${NC}"
    echo -e "${GRAY}  • 輸入 ${WHITE}all${GRAY} 生成所有章節${NC}"
    echo ""
    read -p "範圍: " range_input

    if [ -z "$range_input" ]; then
        echo -e "${YELLOW}已取消${NC}"
        return 0
    fi

    # 解析范围
    local selected_chapters=($(parse_chapter_range "$range_input" "${sorted_available[@]}"))
    if [ $? -ne 0 ] || [ ${#selected_chapters[@]} -eq 0 ]; then
        echo -e "${RED}${ICON_MISSING} 無效的範圍輸入${NC}"
        return 1
    fi

    echo ""
    echo -e "${WHITE}將生成以下 ${#selected_chapters[@]} 個章節：${NC}"
    for chapter in "${selected_chapters[@]}"; do
        echo -e "  ${ICON_CHAPTER} $chapter"
    done
    echo ""

    read -p "是否繼續？ (y/n): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo -e "${YELLOW}已取消${NC}"
        return 0
    fi

    # 定義包裝函數用於並行執行
    generate_audio_wrapper() {
        generate_audio "$1" "true"
    }

    # 並行執行
    local status=0
    if ! parallel_execute generate_audio_wrapper "${selected_chapters[@]}"; then
        status=$?
        echo ""
        echo -e "${YELLOW}${ICON_WARNING} 部分章節處理失敗，請檢查以上訊息${NC}"
    fi

    return $status
}

# 批次生成字幕
batch_generate_subtitles() {
    echo ""
    echo -e "${GREEN}${ICON_SUBTITLE} 生成字幕（可輸入單章或範圍）${NC}"
    echo -e "${GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    local chapters=($(scan_chapters))
    local pending=()

    for entry in "${chapters[@]}"; do
        IFS='|' read -r chapter has_source has_script has_audio has_subtitle <<< "$entry"
        if [ "$has_script" = "true" ] && [ "$has_audio" = "true" ] && [ "$has_subtitle" != "true" ]; then
            pending+=("$chapter")
        fi
    done

    if [ ${#pending[@]} -eq 0 ]; then
        echo -e "${YELLOW}${ICON_WARNING} 沒有需要生成字幕的章節${NC}"
        echo -e "${GRAY}（需同時具備腳本與音頻、且尚未生成字幕）${NC}"
        return 0
    fi

    # 自然排序
    local sorted_pending=($(sort_chapters_naturally "${pending[@]}"))

    echo -e "${WHITE}找到 ${#sorted_pending[@]} 個可生成字幕的章節：${NC}"
    local idx=0
    for chapter in "${sorted_pending[@]}"; do
        echo -e "  ${GRAY}[$idx]${NC} ${ICON_CHAPTER} $chapter"
        ((idx++))
    done
    echo ""

    echo -e "${CYAN}請輸入要生成的章節範圍（索引從 0 開始）：${NC}"
    echo -e "${GRAY}  • 範例: ${WHITE}0-5${GRAY} (生成前 6 章)${NC}"
    echo -e "${GRAY}  • 範例: ${WHITE}0,2,4${GRAY} (生成第 0, 2, 4 章)${NC}"
    echo -e "${GRAY}  • 範例: ${WHITE}1-3,7-9${GRAY} (生成第 1-3 和 7-9 章)${NC}"
    echo -e "${GRAY}  • 輸入 ${WHITE}all${GRAY} 生成所有章節${NC}"
    echo ""
    read -p "範圍: " range_input

    if [ -z "$range_input" ]; then
        echo -e "${YELLOW}已取消${NC}"
        return 0
    fi

    # 解析范围
    local selected_chapters=($(parse_chapter_range "$range_input" "${sorted_pending[@]}"))
    if [ $? -ne 0 ] || [ ${#selected_chapters[@]} -eq 0 ]; then
        echo -e "${RED}${ICON_MISSING} 無效的範圍輸入${NC}"
        return 1
    fi

    echo ""
    echo -e "${WHITE}將生成以下 ${#selected_chapters[@]} 個章節：${NC}"
    for chapter in "${selected_chapters[@]}"; do
        echo -e "  ${ICON_CHAPTER} $chapter"
    done
    echo ""

    read -p "是否繼續？ (y/n): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo -e "${YELLOW}已取消${NC}"
        return 0
    fi

    # 串行執行（字幕生成是 CPU/GPU 密集型任務）
    echo -e "${GRAY}⏱️  串行執行 ${#selected_chapters[@]} 個任務...${NC}"
    echo ""

    local success=0
    local failed=0
    for chapter in "${selected_chapters[@]}"; do
        echo ""
        echo -e "${BLUE}正在處理: $chapter${NC}"
        if generate_subtitles "$chapter" "true" "true"; then
            ((success++))
        else
            ((failed++))
        fi
    done

    echo ""
    echo -e "${WHITE}串行執行完成！${NC}"
   echo -e "  成功: ${GREEN}$success${NC}"
   echo -e "  失敗: ${RED}$failed${NC}"

    if [ "$failed" -gt 0 ]; then
        echo ""
        echo -e "${YELLOW}${ICON_WARNING} 部分章節處理失敗，請檢查以上訊息${NC}"
        return "$failed"
    fi

    return 0
}

# 主選單
show_main_menu() {
    echo -e "${WHITE}請選擇操作：${NC}"
    echo ""
    echo -e "${GREEN}📝 腳本生成${NC}"
    echo -e "  ${BLUE}1)${NC} 生成腳本 ${GRAY}(0 起索引，可輸入單章或範圍，🚀 並行)${NC}"
    echo ""
    echo -e "${PURPLE}🎵 音頻生成${NC}"
    echo -e "  ${BLUE}2)${NC} 生成音頻 ${GRAY}(需先有腳本，可輸入單章或範圍，🚀 並行)${NC}"
    echo ""
    echo -e "${CYAN}🧾 字幕生成${NC}"
    echo -e "  ${BLUE}3)${NC} 生成字幕 ${GRAY}(需先有腳本與音頻，可輸入單章或範圍，⏱️  串行)${NC}"
    echo ""
    echo -e "${CYAN}🛠️  工具功能${NC}"
    echo -e "  ${BLUE}4)${NC} 播放章節音訊（同步字幕）"
    echo -e "  ${BLUE}5)${NC} 測試 API 連線"
    echo -e "  ${BLUE}6)${NC} 查看配置說明"
    echo -e "  ${BLUE}7)${NC} 刷新顯示"
    echo ""
    echo -e "  ${BLUE}0)${NC} 退出"
    echo ""
}

# ============================================================================
# 主程式
# ============================================================================

main() {
    while true; do
        show_header
        display_chapters
        show_main_menu

        read -p "請輸入選項 (0-7): " choice

        case $choice in
            1)
                # 生成腳本（單章或範圍）
                if ! batch_generate_scripts; then
                    echo ""
                    read -p "按 Enter 繼續..."
                    continue
                fi

                echo ""
                read -p "按 Enter 繼續..."
                ;;

            2)
                # 生成音頻（單章或範圍）
                if ! batch_generate_audio; then
                    echo ""
                    read -p "按 Enter 繼續..."
                    continue
                fi

                echo ""
                read -p "按 Enter 繼續..."
                ;;

            3)
                # 生成字幕（單章或範圍）
                if ! batch_generate_subtitles; then
                    echo ""
                    read -p "按 Enter 繼續..."
                    continue
                fi

                echo ""
                read -p "按 Enter 繼續..."
                ;;

            4)
                # 播放章節音訊＋字幕
                echo ""
                local result
                if ! result=$(select_chapter); then
                    echo ""
                    read -p "按 Enter 繼續..."
                    continue
                fi

                IFS='|' read -r chapter has_source has_script has_audio has_subtitle <<< "$result"
                play_audio_with_subtitles "$chapter" "$has_audio" "$has_subtitle"

                echo ""
                read -p "按 Enter 繼續..."
                ;;

            5)
                # 測試 API
                echo ""
                echo -e "${YELLOW}🛠️  測試 API 連線${NC}"
                $PYTHON test_api.py

                echo ""
                read -p "按 Enter 繼續..."
                ;;

            6)
                # 查看配置
                echo ""
                echo -e "${YELLOW}🛠️  配置說明${NC}"
                echo -e "${GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
                echo -e "${WHITE}配置文件：${NC}storytelling_config.yaml"
                echo -e "${WHITE}資料目錄：${NC}$DATA_DIR"
                echo -e "${WHITE}輸出目錄：${NC}$FOUNDATION_DIR"
                echo -e "${WHITE}書籍名稱：${NC}Foundation"

                echo ""
                read -p "按 Enter 繼續..."
                ;;

            7)
                # 刷新顯示（直接重新進入循環）
                continue
                ;;

            0)
                # 退出
                if [ -t 1 ]; then
                    clear
                fi
                echo -e "${GREEN}${ICON_COMPLETE} 感謝使用 Storytelling Podcast 管理工具！${NC}"
                echo ""
                exit 0
                ;;

            *)
                echo ""
                echo -e "${RED}${ICON_MISSING} 無效選項：$choice${NC}"
                echo ""
                read -p "按 Enter 繼續..."
                ;;
        esac
    done
}

# 執行主程式
main
