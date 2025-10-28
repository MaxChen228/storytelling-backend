#!/bin/bash
# 測試所有 6 種模式的腳本

echo "======================================"
echo "測試所有 Gemini API 模式"
echo "======================================"

# 定義所有測試模式
modes=("gemini-flash" "gemini-pro" "單人flash" "單人pro" "對談flash" "對談pro")

# 逐一測試每個模式
for mode in "${modes[@]}"
do
    echo ""
    echo "測試模式: $mode"
    echo "--------------------------------------"
    python test_api.py "$mode"
    
    if [ $? -eq 0 ]; then
        echo "✅ $mode 測試成功"
    else
        echo "❌ $mode 測試失敗"
    fi
    
    echo ""
    sleep 1  # 避免 API 速率限制
done

echo "======================================"
echo "所有測試完成"
echo "======================================"

# 列出生成的音頻檔案
echo ""
echo "生成的音頻檔案："
ls -lh test_*.wav 2>/dev/null || echo "（無音頻檔案）"