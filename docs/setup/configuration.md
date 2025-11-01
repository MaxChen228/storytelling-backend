# 配置指南

完整的 `podcast_config.yaml` 配置參數說明。

## 配置文件位置

```
storytelling-backend/
└── podcast_config.yaml  # 主配置文件
```

## 快速配置

最常用的配置選項：

```yaml
basic:
  english_level: "intermediate"      # beginner / intermediate / advanced
  episode_length: "medium"            # short / medium / long
  narrator_voice: "Aoede"             # Gemini 預設聲音名稱
  start_chapter: 1                    # 從第幾章開始
  chapters_per_run: 1                 # 每次處理幾章
  speaking_pace: "slow"               # slow / neutral / fast
```

## 配置區塊詳解

### 1. 基本設置 (basic)

#### 英語等級 (english_level)

控制腳本的語言教學深度和複雜度。

| 等級 | CEFR | 描述 | 適用對象 |
|------|------|------|----------|
| `beginner` | A2 | 慢速、詳細詞彙解釋、括號翻譯 | 英語初學者 |
| `intermediate` | B1-B2 | 適度講解、讀書會風格 | 中級學習者 |
| `advanced` | C1 | 純故事 + 文學分析、無翻譯 | 高級學習者 |

**配置示例：**
```yaml
storytelling:
  english_levels:
    beginner:
      label: "Beginner Story Guide (A2)"
      pacing: "slow, gentle"
      vocabulary_hint: "Use CEFR A2 vocabulary, keep sentences <= 15 words"
      explanation_style: "Explain new words naturally in simple English..."
      recap_style: "At the end of every segment, recap in simple English"
      narrator_goal: "Be a friendly teacher who retells the story..."
```

#### 節目長度 (episode_length)

控制每集播客的長度和內容密度。

| 長度 | 時長 | 字數 | 區塊數 | 適用場景 |
|------|------|------|--------|----------|
| `short` | 4-6 分鐘 | 650 | 4 | 快速回顧、通勤 |
| `medium` | 7-10 分鐘 | 1100 | 6 | 標準學習、休息時段 |
| `long` | 12-15 分鐘 | 1500 | 8 | 深度學習、專注時段 |

**配置示例：**
```yaml
storytelling:
  lengths:
    medium:
      word_count: 1100
      max_num_chunks: 6
      min_chunk_size: 450
      time_range: "約 7-10 分鐘"
      approach: "完整章節 → 語言提示 → 下集伏筆"
```

#### 旁白聲音 (narrator_voice)

Gemini TTS 支持的聲音名稱。

**可用聲音：**
- `Aoede` - 女聲，溫暖友善
- `Charon` - 男聲，穩重專業
- `Kore` - 女聲，清晰明快
- `Puck` - 中性聲，活潑有趣
- `Achird` - 女聲，柔和優雅

**配置示例：**
```yaml
basic:
  narrator_voice: "Aoede"
```

**啟用隨機聲線：**

共有三種寫法，擇一即可：

1. 直接將 `narrator_voice` 設為清單，系統會從清單中隨機選一個聲線。

   ```yaml
   basic:
     narrator_voice: ["Aoede", "Puck", "Kore"]
   ```

2. 使用 `"random"` 並提供候選列表：

   ```yaml
   basic:
     narrator_voice: "random"
     narrator_voice_candidates:
       - "Aoede"
       - "Charon"
       - "Puck"
   ```

3. 保留固定聲線設定，但啟用 `narrator_voice_random: true`，可搭配 `narrator_voice_candidates` 自訂候選。

   ```yaml
   basic:
     narrator_voice: "Achird"
     narrator_voice_random: true
     narrator_voice_candidates:
       - "Achird"
       - "Kore"
       - "Puck"
   ```

每次生成腳本時會決定一次聲線並寫入 `metadata.json`，同一批章節會共用同個聲線；若腳本缺少聲線資訊，音頻步驟會從候選列表重新抽選並同步回寫。

#### 語速 (speaking_pace)

控制朗讀速度和節奏。

| 語速 | WPM | 適用場景 |
|------|-----|----------|
| `slow` | ~105 | 初學者、複雜概念 |
| `neutral` | ~130 | 一般內容、標準學習 |
| `fast` | ~160 | 高級學習者、回顧 |

**配置示例：**
```yaml
advanced:
  tts_pace_profiles:
    slow:
      script_hint: "Delivery stays unhurried; articulate each word..."
      tts_hint: "Maintain an unhurried tempo around 105 words per minute..."
```

#### 章節範圍設置

```yaml
basic:
  start_chapter: 3           # 從第 3 章開始
  chapters_per_run: 1        # 每次運行處理 1 章（建議 1-3）
```

### 2. 路徑配置 (paths)

定義所有重要目錄的位置。

```yaml
paths:
  books_root: "./data"                    # 書籍源文件根目錄
  outputs_root: "./output"                # 輸出文件根目錄
  transcripts_root: "./data/transcripts"  # 轉錄文件目錄
```

**實際目錄結構：**
```
project/
├── data/                    # books_root
│   ├── foundation/          # 書籍文件夾
│   │   ├── chapter0.txt
│   │   └── summaries/       # 章節摘要
│   └── transcripts/         # transcripts_root
└── output/                  # outputs_root
    └── foundation/
        └── chapter0/
            ├── podcast_script.txt
            ├── podcast.wav
            └── subtitles.srt
```

### 3. 書籍配置 (books)

#### 默認設置 (defaults)

適用於所有書籍的默認配置。

```yaml
books:
  defaults:
    file_pattern: "chapter*.txt"       # 章節文件命名規則（glob）
    encoding: "utf-8"                  # 文件編碼
    clean_whitespace: true             # 自動清除多餘空行
    title_from_filename: true          # 使用文件名作為標題
    min_words: 0                       # 最少字數（低於此值會跳過）
    summary_subdir: "summaries"        # 摘要子目錄名稱
    summary_suffix: "_summary.txt"     # 摘要文件後綴
```

#### 書籍覆寫設置 (overrides)

為特定書籍自定義配置（覆蓋 defaults）。

```yaml
books:
  overrides:
    foundation:                        # 書籍 ID（目錄名稱）
      display_name: "Foundation"       # 顯示名稱
      file_pattern: "part*.md"         # 自定義文件模式
      book_name: "Isaac Asimov's Foundation"
      min_words: 500                   # 此書專用的最小字數
```

### 4. 敘事風格 (storytelling)

控制腳本的敘事風格和結構。

#### 語調 (tone)

```yaml
storytelling:
  tone:
    - "immersive"      # 沉浸式
    - "expressive"     # 表現力強
    - "warm"           # 溫暖友善
    - "curious"        # 好奇探索
```

#### 敘事結構 (narrative_structure)

定義每集播客的結構框架。

```yaml
storytelling:
  narrative_structure:
    - "Hook: lead in with one sentence that sets the chapter context..."
    - "Scene Painting: use sensory details to build the setting"
    - "Conflict or Discovery: show the protagonist's decision..."
    - "Language Spotlight: highlight and explain one or two words..."
    - "Takeaway: wrap the chapter message and plant a teaser..."
```

#### 參與提示 (engagement_prompts)

鼓勵聽眾互動的技巧。

```yaml
storytelling:
  engagement_prompts:
    - "Invite listeners to picture the scene"
    - "Ask an open-ended question"
    - "Use a metaphor that ties back to daily life"
    - "Pause briefly before giving the language cue"
```

#### 感官焦點 (sensory_focus)

強調的感官體驗。

```yaml
storytelling:
  sensory_focus:
    - "sound"      # 聲音
    - "light"      # 光線
    - "texture"    # 質感
    - "emotion"    # 情感
```

#### 創意程度 (creativity)

控制 LLM 生成的隨機性（0.0-1.0）。

```yaml
storytelling:
  creativity: 0.65   # 建議範圍 0.6-0.7
```

### 5. 高級設置 (advanced)

#### 模型選擇

```yaml
advanced:
  llm_model: "gemini-2.5-pro"                  # 腳本生成模型
  tts_model: "gemini-2.5-flash-preview-tts"    # 音頻生成模型
  language: "English"                          # 目標語言
```

### 6. 字幕對齊配置 (alignment)

Montreal Forced Aligner 設置。

```yaml
alignment:
  mfa:
    micromamba_bin: "/opt/homebrew/opt/micromamba/bin/micromamba"
    env_name: "aligner"
    dictionary: "english_mfa"        # 發音字典
    acoustic_model: "english_mfa"    # 聲學模型
    temp_root: "./.mfa_work"         # 臨時工作目錄
    keep_intermediate: false         # 是否保留中間文件
    keep_workdir: false              # 是否保留工作目錄
    extra_args:
      - "--clean"                    # 清理舊文件
      - "--disable_mp"               # 禁用多進程（避免衝突）
```

**查找 micromamba 路徑：**
```bash
which micromamba
# macOS Homebrew: /opt/homebrew/opt/micromamba/bin/micromamba
# Linux: /usr/local/bin/micromamba
```

## 完整配置示例

```yaml
# 基本設置
basic:
  english_level: "intermediate"
  episode_length: "medium"
  narrator_voice: "Aoede"
  start_chapter: 1
  chapters_per_run: 1
  speaking_pace: "slow"

# 路徑
paths:
  books_root: "./data"
  outputs_root: "./output"
  transcripts_root: "./data/transcripts"

# 書籍
books:
  defaults:
    file_pattern: "chapter*.txt"
    encoding: "utf-8"
    clean_whitespace: true
    title_from_filename: true
    min_words: 0
    summary_subdir: "summaries"
    summary_suffix: "_summary.txt"
  overrides:
    foundation:
      display_name: "Foundation"
      book_name: "Isaac Asimov's Foundation"

# 敘事風格
storytelling:
  tone: ["immersive", "expressive", "warm", "curious"]
  narrative_structure:
    - "Hook: lead in with context"
    - "Scene Painting: build the setting"
    - "Conflict or Discovery: key insight"
    - "Language Spotlight: explain phrases"
    - "Takeaway: wrap and tease next episode"
  engagement_prompts:
    - "Invite listeners to picture the scene"
    - "Ask an open-ended question"
  sensory_focus: ["sound", "light", "texture", "emotion"]
  creativity: 0.65

# 高級設置
advanced:
  llm_model: "gemini-2.5-pro"
  tts_model: "gemini-2.5-flash-preview-tts"
  language: "English"

# 字幕對齊
alignment:
  mfa:
    micromamba_bin: "/opt/homebrew/opt/micromamba/bin/micromamba"
    env_name: "aligner"
    dictionary: "english_mfa"
    acoustic_model: "english_mfa"
    temp_root: "./.mfa_work"
    keep_intermediate: false
    keep_workdir: false
    extra_args:
      - "--clean"
      - "--disable_mp"
```

## 配置最佳實踐

### 1. 針對不同受眾

**初學者：**
```yaml
basic:
  english_level: "beginner"
  episode_length: "short"
  speaking_pace: "slow"
```

**中級學習者：**
```yaml
basic:
  english_level: "intermediate"
  episode_length: "medium"
  speaking_pace: "neutral"
```

**高級學習者：**
```yaml
basic:
  english_level: "advanced"
  episode_length: "long"
  speaking_pace: "fast"
```

### 2. 性能優化

```yaml
basic:
  chapters_per_run: 3  # 批次處理提高效率

alignment:
  mfa:
    keep_intermediate: false  # 節省磁盤空間
    keep_workdir: false
```

### 3. 質量優先

```yaml
advanced:
  llm_model: "gemini-2.5-pro"  # 使用最佳模型

storytelling:
  creativity: 0.65  # 平衡創意與準確性
```

## 配置驗證

驗證配置是否正確：

```bash
# 使用 Python 檢查配置
python -c "
import yaml
with open('podcast_config.yaml', 'r') as f:
    config = yaml.safe_load(f)
    print('✅ 配置文件格式正確')
    print(f\"英語等級: {config['basic']['english_level']}\")
    print(f\"節目長度: {config['basic']['episode_length']}\")
"
```

## 常見配置問題

### 問題 1: 腳本太長或太短

**調整：**
```yaml
storytelling:
  lengths:
    medium:
      word_count: 1500  # 增加字數
```

### 問題 2: 語速不合適

**調整：**
```yaml
basic:
  speaking_pace: "slow"  # 改為 slow / neutral / fast
```

### 問題 3: 找不到章節文件

**檢查：**
```yaml
books:
  defaults:
    file_pattern: "chapter*.txt"  # 確保與實際文件名匹配
```

### 問題 4: MFA 對齊失敗

**檢查 micromamba 路徑：**
```bash
which micromamba
# 更新配置中的路徑
```

## 環境變量配置

除了 YAML 配置，還可以使用環境變量覆寫某些設置：

```bash
# .env 文件
GEMINI_API_KEY=your_api_key
STORY_BOOK_ID=foundation           # 默認書籍 ID
PODCAST_SCRIPT_BATCH_SIZE=10       # 腳本批次大小
PODCAST_AUDIO_BATCH_SIZE=5         # 音頻批次大小
PODCAST_ENV_PATH=/custom/path/.venv  # 自定義虛擬環境路徑
```

## 下一步

配置完成後：
- 查看 [CLI 使用指南](../usage/cli-guide.md) 了解如何運行
- 查看 [工作流程指南](../usage/workflow.md) 了解最佳實踐
- 查看 [故障排除](../operations/troubleshooting.md) 解決常見問題

## 參考資料

- [Gemini API 文檔](https://ai.google.dev/docs)
- [Montreal Forced Aligner 文檔](https://montreal-forced-aligner.readthedocs.io/)
- [YAML 語法指南](https://yaml.org/spec/)
