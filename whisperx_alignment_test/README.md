# WhisperX 強制對齊測試目錄

## 目的
使用 WhisperX 實現音頻-腳本強制對齊 (Forced Alignment)，為每個詞獲得精確的時間戳。

## 目錄結構
```
whisperx_alignment_test/
├── README.md                  # 說明文件
├── scripts/                   # 對齊腳本
│   ├── text_cleaner.py       # 腳本清理工具
│   ├── align_audio.py        # 主要對齊腳本
│   └── generate_srt.py       # SRT 字幕生成
├── test_data/                # 測試數據
│   ├── podcast.wav           # chapter3 音頻（30MB, 24kHz mono）
│   └── podcast_script.txt    # chapter3 腳本（1203 words）
└── output/                   # 輸出結果
    ├── aligned_transcript.json  # 詞級時間戳
    └── subtitles.srt           # SRT 字幕文件

## 測試案例
- **音頻**: chapter0 podcast (~6 分鐘, 18MB)
- **語言**: English
- **說話者**: 單一旁白 (Leda voice)

## 使用步驟

### 1. 安裝依賴
```bash
cd "/Users/chenliangyu/Desktop/story telling podcast"
source venv/bin/activate
pip install whisperx
```

### 2. 執行對齊
```bash
cd whisperx_alignment_test
python scripts/align_audio.py
```

### 3. 查看結果
```bash
# JSON 格式（詞級時間戳）
cat output/aligned_transcript.json

# SRT 字幕
cat output/subtitles.srt
```

### 4. 動態播放（可選）
```bash
python scripts/play_with_subtitles.py test_data/podcast.wav output/subtitles.srt
```
- 同步播放音頻並在終端即時切換字幕。
- `--player` 可覆寫播放器（預設依序探測 `ffplay`/`afplay`/`mpv`）。
- `--mute` 只跑字幕，`--limit 10` 僅預覽前 10 行，方便測試。

## 預期輸出

### aligned_transcript.json
```json
{
  "segments": [
    {
      "start": 0.0,
      "end": 5.2,
      "text": "Welcome to Storytelling Series",
      "words": [
        {"word": "Welcome", "start": 0.0, "end": 0.6, "score": 0.98}
      ]
    }
  ]
}
```

### subtitles.srt
```srt
1
00:00:00,000 --> 00:00:00,600
Welcome

2
00:00:00,650 --> 00:00:00,750
to
```

## 技術細節

### 音頻格式
- 格式: WAV (RIFF, little-endian)
- 採樣率: 24000 Hz
- 位深度: 16-bit
- 聲道: Mono
- 大小: ~30MB

### 腳本處理
需要清理的元素：
- 暫停標記: `(pause)`
- 中文註釋: `Nerves (緊張)`
- 特殊格式: 括號、破折號

### WhisperX 配置
```python
device = "mps"  # Apple Silicon GPU (備用: "cpu")
compute_type = "float16"
language = "en"
```

## 性能預估
- CPU 模式: ~5-10 分鐘
- MPS 模式: ~2-5 分鐘

## 下一步
成功後整合進主工作流程：
1. 添加進 `run.sh` 主選單
2. 批次處理所有章節
3. 生成互動式學習工具
