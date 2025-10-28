# Storytelling Backend

單人旁白播客生成系統 - 後端服務

## 功能概述

- 📝 將英文書籍章節轉換為教學風格的單人旁白腳本
- 🎙️ 使用 Gemini TTS 生成高質量音頻
- 📊 生成詞級精準字幕（WhisperX）
- 🚀 FastAPI 後端 API 服務
- ⚙️ 支持批次處理和並行執行

## 快速開始

### 1. 環境設置

```bash
# 創建虛擬環境
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate  # Windows

# 安裝依賴
pip install -r requirements/base.txt
pip install -r requirements/server.txt
pip install -r requirements/subtitle.txt
```

### 2. 配置環境變量

創建 `.env` 文件：

```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. 運行腳本生成

```bash
# 交互式運行
./run.sh

# 或直接生成特定章節
python generate_script.py data/foundation chapter1
python generate_audio.py data/foundation_processed_scripts/chapter1
python generate_subtitles.py data/foundation_processed_scripts/chapter1
```

### 4. 啟動 API 服務器

```bash
# 開發模式
uvicorn server.app.main:app --reload --host 0.0.0.0 --port 8000

# 訪問 API 文檔
open http://localhost:8000/docs
```

## 主要命令

### run.sh 交互式菜單

```bash
./run.sh

選項：
1. 書籍預處理（章節分割、摘要生成）
2. 批次生成腳本（支持範圍選擇，如 1-5,7-9）
3. 批次生成音頻（並行執行）
4. 批次生成字幕（串行執行）
5. 單章完整流程
6. 範圍完整流程
```

### 配置文件

- `podcast_config.yaml` - 主配置（語言級別、長度、風格）
- `.env` - API 金鑰和環境變量

## API 端點

### 書籍列表
```http
GET /api/books
```

### 章節列表
```http
GET /api/books/{book_id}/chapters
```

### 章節詳情（含音頻 URL 和字幕）
```http
GET /api/books/{book_id}/chapters/{chapter_id}
```

### 音頻文件下載
```http
GET /api/audio/{book_id}/{chapter_id}
```

## 技術棧

- **腳本生成**: Google Gemini 2.5 Pro
- **TTS**: Gemini Multi-Speaker TTS (單人模式)
- **字幕對齊**: WhisperX (Whisper + 強制對齊)
- **API 框架**: FastAPI
- **任務隊列**: Celery (可選)
- **Python**: 3.12+

## 目錄結構

```
storytelling-backend/
├── generate_script.py      # 腳本生成器
├── generate_audio.py        # 音頻生成器
├── generate_subtitles.py    # 字幕生成器
├── run.sh                   # 主入口 CLI
├── podcast_config.yaml      # 主配置文件
├── server/                  # FastAPI 服務
│   └── app/
│       ├── main.py         # API 端點定義
│       ├── schemas.py      # Pydantic 模型
│       └── services/       # 業務邏輯
├── whisperx_alignment_test/ # 字幕生成測試
├── requirements/            # 依賴管理
│   ├── base.txt            # 核心依賴
│   ├── server.txt          # API 服務依賴
│   └── subtitle.txt        # 字幕生成依賴
├── data/                    # 書籍數據
└── output/                  # 生成結果（已忽略）
```

## 常見問題

### 字幕飆速問題
已修復：使用 Whisper 原生時間戳 + 強制對齊，不再使用固定語速估算。

### 雙人對話標籤
已清理：生成的腳本自動移除 `<Person1>` 等標籤，適配單人旁白模式。

### 並行執行
- 腳本生成：✅ 並行（Gemini API 調用）
- 音頻生成：✅ 並行（Gemini TTS）
- 字幕生成：❌ 串行（CPU/GPU 密集，避免資源競爭）

## 許可證

MIT License
