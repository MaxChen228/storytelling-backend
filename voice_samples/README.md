# Gemini Voice Samples

這個資料夾提供批次產生 Gemini TTS 聲線樣本的工具。

## 檔案說明
- `generate_voice_samples.py`：主腳本，使用 Cloud Text-to-Speech API 生成指定聲線的試聽檔。
- `config.yaml`：範例設定，可調整要生成的聲線清單、取樣文字與輸出路徑。

## 使用方式
```bash
source .venv/bin/activate
python voice_samples/generate_voice_samples.py --config voice_samples/config.yaml
```

### 客製參數
- `--voices`：直接在命令列指定聲線（優先於設定檔）。
- `--text`：覆寫要朗讀的樣本文字。
- `--language-code`：當聲線名稱無法推斷語言時的預設語言碼。
- `--model`：指定預設使用的 Gemini TTS 模型（如 `gemini-2.5-flash-tts`）。
- `--overwrite`：重新產生已存在的檔案。

### 產出
- 預設會把 WAV 檔與對應 `.json` metadata 寫入 `output/voice_samples/`。
- 可在 `config.yaml` 或命令列透過 `--output-dir` 指定其它路徑。

## 注意事項
- 確保 `.env` 或系統環境已設 `GOOGLE_APPLICATION_CREDENTIALS` 指向擁有 Text-to-Speech 權限的服務帳戶金鑰。
- 聲線名稱需使用 Cloud Text-to-Speech 的 Gemini TTS 聲線 ID，例如 `en-US-LedaNeural`。
