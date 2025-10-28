# .env 到 podcast_config.yaml 遷移指南

## 📊 參數遷移對照表

### ✅ 已遷移到 podcast_config.yaml 的參數

| .env 參數 | podcast_config.yaml 位置 | 說明 |
|----------|-------------------------|------|
| `DEFAULT_ENGLISH_LEVEL` | `basic.english_level` | 英語等級 |
| `DEFAULT_TARGET_MINUTES` | `basic.target_minutes` | 目標時長 |
| `DEFAULT_STYLE_INSTRUCTIONS` | `basic.style_instructions` | 風格指令 |
| `GEMINI_LLM_MODEL` | `advanced.llm_model` | LLM 模型 |
| `GEMINI_TTS_MODEL` | `advanced.tts_model` | TTS 模型 |
| `GEMINI_HOST_VOICE` | `voices.host_voice` | 主持人聲線 |
| `GEMINI_EXPERT_VOICE` | `voices.expert_voice` | 專家聲線 |
| `OUTPUT_BASE_DIR` | `advanced.output_dir` | 輸出目錄 |

### 🔑 保留在 .env 的參數（敏感資訊）

| 參數 | 用途 | 必需性 |
|-----|------|-------|
| `GEMINI_API_KEY` | Gemini API 認證 | **必需** |
| `OPENAI_API_KEY` | OpenAI API 認證 | 可選（使用 Podcastfy TTS 時需要） |
| `ELEVENLABS_API_KEY` | ElevenLabs API 認證 | 可選 |

### ⚠️ 已廢棄的參數

以下參數不再使用，可以安全刪除：

- `DEFAULT_LLM_PROVIDER` - 現在自動根據 API Key 判斷
- `DEFAULT_TTS_PROVIDER` - 由 `use_podcastfy_tts` 控制
- `WORDS_PER_MINUTE` - 使用社區最佳實踐計算
- `AUDIO_*` 設定 - 硬編碼為 Gemini TTS 標準
- 所有 Feature Flags - 移至 podcast_config.yaml 或程式邏輯

## 🚀 遷移步驟

### 1. 備份現有 .env
```bash
cp .env .env.backup
```

### 2. 使用精簡版 .env
```bash
cp .env.minimal .env
```

### 3. 確認 podcast_config.yaml 設定
檢查所有參數是否已正確設定在 `podcast_config.yaml`

### 4. 測試
```bash
python step1_generate_script.py
python step2_generate_audio.py
```

## 📝 為什麼要遷移？

1. **關注點分離**：
   - `.env` = 敏感資訊（API Keys）
   - `podcast_config.yaml` = 應用設定

2. **版本控制友好**：
   - `.env` 不應該進版本控制（包含 API Keys）
   - `podcast_config.yaml` 可以安全地進版本控制

3. **使用便利**：
   - YAML 格式更易讀、支援註解
   - 集中管理所有播客生成參數

## 🔍 驗證遷移成功

執行以下命令確認系統正常運作：

```python
# 檢查 API Key
import os
from dotenv import load_dotenv
load_dotenv()
print("Gemini API Key:", "✅" if os.getenv("GEMINI_API_KEY") else "❌")

# 檢查配置文件
import yaml
with open("podcast_config.yaml") as f:
    config = yaml.safe_load(f)
print("Config loaded:", "✅" if config else "❌")
```

## ⚡ 快速參考

### 最小化 .env（必需）
```env
GEMINI_API_KEY=your-api-key
```

### 主要配置（podcast_config.yaml）
```yaml
basic:
  english_level: "B2"
  target_minutes: 3
  
voices:
  host_voice: "Kore"
  expert_voice: "Puck"
  
input:
  source: "your-content"
  type: "auto"
```