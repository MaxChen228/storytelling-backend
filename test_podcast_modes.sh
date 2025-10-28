#!/bin/bash
# 測試三種播客長度模式

echo "======================================"
echo "測試播客長度模式系統"
echo "======================================"
echo ""

# 定義顏色
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 測試單一模式函數
test_mode() {
    local mode=$1
    echo -e "${BLUE}測試 $mode 模式...${NC}"
    echo "--------------------------------------"
    
    # 修改配置文件
    python3 -c "
import yaml
with open('podcast_config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)
config['basic']['podcast_length'] = '$mode'
with open('podcast_config.yaml', 'w', encoding='utf-8') as f:
    yaml.dump(config, f, allow_unicode=True)
print(f'已設定為 {mode} 模式')
"
    
    # 執行腳本生成（只生成不執行音頻）
    python3 generate_script.py
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $mode 模式測試成功${NC}"
        
        # 顯示生成的腳本統計
        latest_dir=$(ls -td output/scripts/*/ | head -1)
        if [ -f "$latest_dir/metadata.json" ]; then
            echo "📊 生成統計："
            python3 -c "
import json
with open('$latest_dir/metadata.json', 'r') as f:
    data = json.load(f)
    print(f\"   - 時間範圍: {data.get('time_range', 'N/A')}\")
    print(f\"   - 實際字數: {data.get('actual_words', 'N/A')}\")
    print(f\"   - 目標字數: {data.get('target_words', 'N/A')}\")
"
        fi
    else
        echo -e "${RED}❌ $mode 模式測試失敗${NC}"
    fi
    
    echo ""
    sleep 2  # 避免 API 速率限制
}

# 主程式
if [ "$1" ]; then
    # 測試指定模式
    if [[ "$1" == "short" || "$1" == "medium" || "$1" == "long" ]]; then
        test_mode "$1"
    else
        echo -e "${RED}錯誤：未知的模式 '$1'${NC}"
        echo "可用模式：short, medium, long"
        exit 1
    fi
else
    # 測試所有模式
    echo "將測試所有三種模式..."
    echo ""
    
    for mode in short medium long
    do
        test_mode "$mode"
    done
    
    echo "======================================"
    echo -e "${GREEN}所有模式測試完成！${NC}"
    echo "======================================"
fi

# 提示下一步
echo ""
echo "💡 提示："
echo "1. 查看生成的腳本：ls -la output/scripts/"
echo "2. 生成音頻：python generate_audio.py [腳本目錄]"
echo "3. 使用工作流：python podcast_workflow.py --mode dev"