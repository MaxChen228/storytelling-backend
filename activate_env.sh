#!/bin/bash
# 激活虛擬環境的便捷腳本

export PODCAST_ENV_PATH=/Users/chenliangyu/Desktop/podcast-workspace/storytelling-backend/.venv

# 如果直接執行這個腳本，啟動一個新的 shell
if [ "$0" = "${BASH_SOURCE[0]}" ]; then
    echo "✅ 已設置環境變量 PODCAST_ENV_PATH"
    echo "📂 虛擬環境: $PODCAST_ENV_PATH"
    echo ""
    echo "現在可以運行："
    echo "  ./run.sh                    # CLI 交互式菜單"
    echo "  uvicorn server.app.main:app # 啟動 FastAPI"
    echo ""
    exec bash
fi
