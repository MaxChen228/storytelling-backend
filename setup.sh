#!/bin/bash

set -euo pipefail

# 🎙️ Storytelling Podcast - 環境初始化
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_NAME="storytelling"
VENV_PATH="$ROOT_DIR/.venvs/$PROJECT_NAME"
BOOTSTRAP="$ROOT_DIR/scripts/bootstrap_venv.sh"
MIN_PY_VERSION="3.9"

echo "🎙️ Storytelling Podcast - 環境初始化"
echo "==================================="

# Python 版本檢查
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}✗ 找不到 python3，請安裝 Python ${MIN_PY_VERSION}+${NC}"
    exit 1
fi
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓ 偵測到 Python $python_version${NC}"

# ffmpeg 檢查
if command -v ffmpeg >/dev/null 2>&1; then
    echo -e "${GREEN}✓ ffmpeg 已安裝${NC}"
else
    echo -e "${RED}✗ 未找到 ffmpeg，請先透過 brew install ffmpeg 或 apt 安裝${NC}"
    exit 1
fi

# 建立 / 更新虛擬環境
echo -e "${YELLOW}→ 建立或更新虛擬環境...${NC}"
bash "$BOOTSTRAP" "$PROJECT_NAME"

# 驗證安裝
# shellcheck disable=SC1090
source "$VENV_PATH/bin/activate"
python -c "import podcastfy; print('✓ Podcastfy 版本：', getattr(podcastfy, '__version__', 'unknown'))"
deactivate >/dev/null

# 檢查 API Key
if [ -f "$SCRIPT_DIR/.env" ]; then
    if grep -q "GEMINI_API_KEY" "$SCRIPT_DIR/.env"; then
        echo -e "${GREEN}✓ .env 已設置 GEMINI_API_KEY${NC}"
    else
        echo -e "${YELLOW}⚠️  .env 尚未填寫 GEMINI_API_KEY${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  找不到 .env，請建立並填入 API Key${NC}"
fi

# 建立輸出資料夾
mkdir -p "$SCRIPT_DIR/output" "$SCRIPT_DIR/output_advanced" "$SCRIPT_DIR/cache"
echo -e "${GREEN}✓ 輸出目錄就緒${NC}"

echo ""
echo -e "${CYAN}完成！${NC} 後續指令："
echo -e "  1. ${YELLOW}source $VENV_PATH/bin/activate${NC}"
echo -e "  2. ${YELLOW}python podcast_workflow.py --mode dev${NC}"
