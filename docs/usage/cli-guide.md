# CLI 使用指南

`run.sh` 交互式命令行界面完整使用說明。

## 快速開始

```bash
cd storytelling-backend
./run.sh
```

## 主界面概覽

啟動 CLI 後，會看到以下界面：

```
┌────────────────────────────────────────────────────────────┐
│ Idx │ Chapter  │ Source │ Summary │ Script │ Audio │ Subtitle │
├────────────────────────────────────────────────────────────┤
│ 0   │ chapter0 │ ✓      │ ✓       │ ✓      │ ✓     │ ✓        │
│ 1   │ chapter1 │ ✓      │ ✓       │ ✓      │ ✗     │ ✗        │
│ 2   │ chapter2 │ ✓      │ ✗       │ ✗      │ ✗     │ ✗        │
└────────────────────────────────────────────────────────────┘

操作選單：
  1) 生成腳本
  2) 生成音頻
  3) 生成字幕
  4) 生成摘要
  5) 播放音頻
  6) 切換書籍
  r) 重新整理
  q) 離開
```

**狀態圖標說明：**
- ✓ - 文件存在
- ✗ - 文件不存在

## 功能詳解

### 1) 生成腳本

將書籍章節轉換為播客腳本。

**流程：**
```
選擇操作 → 輸入章節範圍 → 批次處理 → 顯示結果
```

**支持的章節選擇格式：**
- `0` - 單一章節（索引 0）
- `0-5` - 範圍選擇（章節 0 到 5）
- `0,2,4` - 多個章節（章節 0、2、4）
- `0-5,7-9` - 混合格式（章節 0-5 和 7-9）
- `all` 或 `a` - 所有可用章節

**示例：**
```
> 1
可處理章節（索引從 0 開始）：
  [0] chapter0
  [1] chapter1
  [2] chapter2

請輸入章節範圍（如 0-5,7-9 或 all）：
> 0-1

共 2 章節，腳本批次大小 10，共 1 批。

📝 生成腳本：chapter0
✅ 腳本完成：chapter0

📝 生成腳本：chapter1
✅ 腳本完成：chapter1

✅ 全部 腳本 任務完成
```

**前置條件：**
- 必須存在源文件：`data/{book_id}/{chapter}.txt`

**輸出位置：**
- `output/{book_id}/{chapter}/podcast_script.txt`
- `output/{book_id}/{chapter}/metadata.json`

**批次處理設置：**
```bash
# 通過環境變量調整
export PODCAST_SCRIPT_BATCH_SIZE=10   # 每批處理數量
export PODCAST_SCRIPT_BATCH_DELAY=10  # 批次間延遲（秒）
```

### 2) 生成音頻

將腳本轉換為音頻文件。需要字幕時，再執行選項 3）。

**流程：**
```
選擇操作 → 輸入章節範圍 → 批次處理 → 顯示結果
```

**示例：**
```
> 2
可處理章節（索引從 0 開始）：
  [0] chapter1

請輸入章節範圍（如 0-5,7-9 或 all）：
> 0

共 1 章節，音頻批次大小 5，共 1 批。

🎵 生成音頻：chapter1
⏭️ 已跳過字幕對齊 (--align 可啟用)
✅ 音頻完成：chapter1

✅ 全部 音頻 任務完成
```

**前置條件：**
- 必須已生成腳本：`output/{book_id}/{chapter}/podcast_script.txt`

**輸出位置：**
- `output/{book_id}/{chapter}/podcast.wav` - 原始音頻（保留給字幕對齊等流程）
- `output/{book_id}/{chapter}/podcast.mp3` - 壓縮音頻，適合上傳/播放
- `output/{book_id}/{chapter}/subtitles.srt` - 字幕文件（自動生成）

> 小提醒：如果有舊章節只有 WAV，可執行 `scripts/convert_wav_to_mp3.py` 一次性補齊 MP3。

**批次處理設置：**
```bash
export PODCAST_AUDIO_BATCH_SIZE=5     # 每批處理數量
export PODCAST_AUDIO_BATCH_DELAY=60   # 批次間延遲（秒）
```

**自動字幕生成：**
- 使用 Montreal Forced Aligner
- 詞級精準對齊
- 無需手動執行字幕生成

### 3) 生成字幕

重新生成或更新字幕文件。

**用途：**
- 重新生成已損壞的字幕
- 使用新的對齊參數
- 修復字幕同步問題

**流程：**
```
選擇操作 → 輸入章節範圍 → 串行處理 → 顯示結果
```

**示例：**
```
> 3
可處理章節（索引從 0 開始）：
  [0] chapter0

請輸入章節範圍（如 0-5,7-9 或 all）：
> 0

🧾 生成字幕：chapter0
✅ 字幕完成：chapter0
```

**前置條件：**
- 必須已生成腳本和音頻

**輸出位置：**
- `output/{book_id}/{chapter}/subtitles.srt`

**注意事項：**
- 字幕生成為串行處理（CPU 密集）
- 不支持批次並行執行

### 4) 生成摘要

預處理章節，生成濃縮摘要。

**用途：**
- 為腳本生成提供上下文
- 支持前情回顧和下集預告
- 加速後續腳本生成

**流程：**
```
選擇操作 → 輸入範圍 → 選擇覆寫選項 → 執行
```

**示例：**
```
> 4
📚 生成摘要

輸入起始章節（1-based，預設 1）：
> 1

輸入結束章節（1-based，預設至最後一章，留空代表全部）：
> 3

是否覆寫已存在摘要？ (y/N)：
> n

ℹ️ 命令：python preprocess_chapters.py --config podcast_config.yaml --book-id foundation --start-chapter 1 --end-chapter 3

[執行摘要生成...]
```

**輸出位置：**
- `data/{book_id}/summaries/{chapter}_summary.txt`

**注意事項：**
- 章節編號為 1-based（從 1 開始）
- 預設不覆寫已存在的摘要
- 使用 `--force` 可強制重新生成

### 5) 播放音頻

播放已生成的音頻文件（支持字幕顯示）。

**流程：**
```
選擇操作 → 選擇章節 → 播放
```

**示例：**
```
> 5
  [0] chapter0

請輸入章節索引：
> 0

▶️ 播放：chapter0
[啟動播放器...]
```

**播放器優先順序：**
1. `play_with_subtitles.py` - 如果存在字幕（推薦）
2. `afplay` - macOS 默認播放器
3. `ffplay` - FFmpeg 播放器
4. 手動播放提示

**快捷鍵（play_with_subtitles.py）：**
- `Space` - 播放/暫停
- `→` - 快進 5 秒
- `←` - 快退 5 秒
- `q` - 退出

### 6) 切換書籍

在多本書籍之間切換。

**流程：**
```
選擇操作 → 查看書籍列表 → 選擇書籍
```

**示例：**
```
> 6

可用書籍：

  [0] Foundation (章節: 10, 已有摘要: 10)
  [1] Dune (章節: 15, 已有摘要: 0)

請輸入書籍索引（或 q 離開）：
> 1

📚 已切換到「Dune」
```

**書籍檢測：**
- 自動掃描 `data/` 目錄
- 顯示章節總數和摘要數量
- 支持多本書籍並行管理

### r) 重新整理

刷新章節狀態顯示。

**用途：**
- 手動添加/刪除文件後更新顯示
- 查看最新處理進度
- 驗證操作結果

**示例：**
```
> r
[重新掃描章節...]
[更新狀態表格...]
```

### q) 離開

退出 CLI 程序。

```
> q
再見！
```

## 高級用法

### 批次處理優化

#### 調整批次大小

```bash
# 快速處理（小批次）
export PODCAST_SCRIPT_BATCH_SIZE=3
export PODCAST_AUDIO_BATCH_SIZE=2

# 標準處理
export PODCAST_SCRIPT_BATCH_SIZE=10
export PODCAST_AUDIO_BATCH_SIZE=5

# 大批次處理（注意 API 限制）
export PODCAST_SCRIPT_BATCH_SIZE=20
export PODCAST_AUDIO_BATCH_SIZE=10
```

#### 調整延遲時間

```bash
# 減少延遲（快速處理）
export PODCAST_SCRIPT_BATCH_DELAY=5
export PODCAST_AUDIO_BATCH_DELAY=30

# 增加延遲（避免 API 限制）
export PODCAST_SCRIPT_BATCH_DELAY=30
export PODCAST_AUDIO_BATCH_DELAY=120
```

### 範圍選擇技巧

**選擇前半部章節：**
```
> 0-9
```

**選擇後半部章節：**
```
> 10-19
```

**跳過特定章節：**
```
> 0-4,6-9    # 跳過章節 5
```

**只處理特定章節：**
```
> 0,5,10,15  # 只處理這四章
```

### 自定義虛擬環境

```bash
# 使用自定義虛擬環境路徑
export PODCAST_ENV_PATH=/path/to/custom/.venv
./run.sh
```

## 工作流程示例

### 場景 1: 處理新書籍

```bash
# 1. 準備源文件
ls data/new-book/chapter*.txt

# 2. 啟動 CLI
./run.sh

# 3. 選擇新書籍
> 6
> [選擇新書籍索引]

# 4. 生成摘要（可選但推薦）
> 4
> 1
> [Enter] # 處理全部
> n       # 不覆寫

# 5. 批次生成腳本
> 1
> all

# 6. 批次生成音頻
> 2
> all

# 7. 驗證結果
> 5
> [選擇章節試聽]
```

### 場景 2: 重新生成特定章節

```bash
./run.sh

# 1. 重新生成腳本
> 1
> 3    # 只處理章節 3

# 2. 重新生成音頻
> 2
> 3

# 3. 重新生成字幕（如果需要）
> 3
> 3
```

### 場景 3: 增量處理

```bash
./run.sh

# 1. 查看狀態
[查看表格，發現章節 5-9 未處理]

# 2. 只處理未完成的章節
> 1
> 5-9

> 2
> 5-9
```

## 常見問題

### Q: 如何只生成腳本不生成音頻？
**A:** 使用選項 1）生成腳本，跳過選項 2）。

### Q: 批次處理中途失敗怎麼辦？
**A:** 重新執行相同操作，已完成的章節會自動跳過。

### Q: 如何查看生成進度？
**A:**
- 實時查看終端輸出
- 使用 `r` 刷新狀態表格
- 檢查 `output/` 目錄

### Q: 選擇範圍時出錯怎麼辦？
**A:** 錯誤示例和正確格式：
```
❌ 錯誤: 0 - 5  （有空格）
✅ 正確: 0-5

❌ 錯誤: 0,1,2,  （末尾逗號）
✅ 正確: 0,1,2

❌ 錯誤: 10-5   （範圍倒序）
✅ 正確: 5-10   （會自動修正）
```

### Q: 為什麼音頻生成比腳本生成慢？
**A:** 音頻生成包含：
1. TTS 合成（較慢）
2. 音頻處理
3. MFA 字幕對齊（CPU 密集）

建議使用較小的批次大小和較長的延遲。

### Q: 可以同時處理多本書籍嗎？
**A:** 可以開啟多個終端分別運行 `./run.sh`，或使用選項 6）切換。

## 命令行參數（直接調用 Python）

雖然推薦使用 `run.sh`，但也可以直接調用 Python 腳本：

```bash
# 生成腳本
python generate_script.py chapter0 --book-id foundation --config podcast_config.yaml

# 生成音頻
python generate_audio.py output/foundation/chapter0

# 生成字幕
python generate_subtitles.py output/foundation/chapter0 --config podcast_config.yaml

# 生成摘要
python preprocess_chapters.py --book-id foundation --start-chapter 1 --end-chapter 5
```

## 下一步

- 查看 [工作流程指南](workflow.md) 了解最佳實踐
- 查看 [配置指南](../setup/configuration.md) 自定義設置
- 查看 [故障排除](../operations/troubleshooting.md) 解決問題

## 反饋和建議

如果您有任何建議或發現問題：
- 🐛 [報告問題](https://github.com/your-org/storytelling-backend/issues)
- 💡 [提出功能請求](https://github.com/your-org/storytelling-backend/discussions)
