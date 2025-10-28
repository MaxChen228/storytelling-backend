# Podcastfy conversation_config.yaml 完整參數參考



## 📋 **總覽**



此文件包含所有可用於定製Podcastfy播客生成的參數選項。基於官方文檔和源代碼分析，以下是最完整的參數列表。



-----



## 🎵 **基本播客資訊 (Basic Podcast Information)**



### 播客標識



```yaml

podcast_name: "Your Podcast Name"              # 播客名稱

podcast_tagline: "Your tagline here"           # 播客標語

host_intro: "Welcome to our discussion"        # 主持人開場白

closing_remarks: "Thank you for listening"     # 結束語

```



-----



## 👥 **角色與聲音設定 (Roles & Voice Settings)**



### 角色定義



```yaml

roles_person1: "expert host"                   # 第一人角色（通常是主持人）

roles_person2: "curious learner"               # 第二人角色（通常是學習者/觀眾）

# 可選角色類型:

# - "expert host", "professional narrator", "teacher"

# - "curious learner", "audience participator", "student"

# - "storyteller", "interviewer", "analyst"

```



### ElevenLabs TTS 設定



```yaml

question_voice: "alloy"                        # 提問者聲音

answer_voice: "echo"                           # 回答者聲音

tts_model: "eleven_multilingual_v2"            # ElevenLabs TTS模型



# 可用模型選項:

# - "eleven_multilingual_v2"

# - "eleven_turbo_v2" 

# - "eleven_monolingual_v1"



# ElevenLabs 聲音選項 (部分):

# - "alloy", "echo", "fable", "onyx", "nova", "shimmer"

# - "Alice", "Brian", "Charlie", "Dorothy", "Emily"

```



### OpenAI TTS 設定



```yaml

openai_question_voice: "alloy"                 # OpenAI 提問聲音

openai_answer_voice: "nova"                    # OpenAI 回答聲音

openai_tts_model: "tts-1"                      # OpenAI TTS模型



# OpenAI TTS 模型選項:

# - "tts-1" (標準品質)

# - "tts-1-hd" (高品質)



# OpenAI 聲音選項:

# - "alloy", "echo", "fable", "onyx", "nova", "shimmer"

```



### Google/Gemini TTS 設定



```yaml

gemini_tts_model: "gemini-tts-multi"           # Gemini TTS模型

gemini_speaker_count: 2                        # 說話者數量

```



-----



## 📝 **內容結構與長度 (Content Structure & Length)**



### 對話結構



```yaml

dialogue_structure:                            # 對話結構定義

  - "Introduction"                             # 介紹

  - "Main Discussion"                          # 主要討論

  - "Key Points Analysis"                      # 關鍵點分析

  - "Examples and Applications"                # 實例與應用

  - "Summary and Takeaways"                    # 總結與要點

  - "Conclusion"                               # 結論



# 預設結構選項:

# 教育型: ["Problem Statement", "Concept Explanation", "Examples", "Practice", "Summary"]

# 商業型: ["Executive Summary", "Market Analysis", "Key Insights", "Recommendations"]

# 故事型: ["Scene Setting", "Character Introduction", "Rising Action", "Climax", "Resolution"]

# 新聞型: ["Headlines", "Background", "Key Details", "Analysis", "Implications"]

```



### 長度控制參數



```yaml

word_count: 1500                               # 目標總字數

max_num_chunks: 7                              # 最大討論回合數 (預設: 7)

min_chunk_size: 600                            # 每回合最小字符數 (預設: 600)



# 預設長度模式:

# 短版播客 (2-5分鐘):

#   word_count: 500-800

#   max_num_chunks: 3-5

#   min_chunk_size: 200-400



# 標準播客 (10-15分鐘):

#   word_count: 1200-2000

#   max_num_chunks: 6-8

#   min_chunk_size: 400-600



# 長版播客 (30+分鐘):

#   word_count: 4000-8000

#   max_num_chunks: 12-20

#   min_chunk_size: 800-1200

```



-----



## 🎨 **對話風格與語調 (Conversation Style & Tone)**



### 對話風格



```yaml

conversation_style: "educational_friendly"     # 對話風格



# 可用風格選項:

# - "educational_friendly"        # 教育友善型

# - "professional_concise"        # 專業簡潔型

# - "narrative_engaging"          # 敘述引人入勝型

# - "technical_detailed"          # 技術詳細型

# - "casual_conversational"       # 輕鬆對話型

# - "formal_academic"             # 正式學術型

# - "storytelling_dramatic"       # 故事戲劇型

# - "interview_investigative"     # 訪談調查型

```



### 語調設定



```yaml

tone: "informative_accessible"                 # 整體語調



# 語調選項:

# - "informative_accessible"      # 資訊性且易懂

# - "authoritative_direct"        # 權威直接

# - "friendly_enthusiastic"       # 友善熱情

# - "serious_analytical"          # 嚴肅分析

# - "playful_creative"            # 俏皮創意

# - "empathetic_supportive"       # 同理支持

# - "dramatic_captivating"        # 戲劇引人入勝

# - "neutral_objective"           # 中性客觀

```



### 節奏與互動



```yaml

pace: "moderate"                               # 語速節奏



# 節奏選項:

# - "slow"           # 慢速 (教育、複雜概念)

# - "moderate"       # 中速 (一般內容)

# - "fast"           # 快速 (新聞、商業摘要)

# - "varied"         # 變化 (故事、戲劇)



interaction_level: "high"                      # 互動程度



# 互動程度:

# - "low"            # 低互動 (單人敘述)

# - "medium"         # 中互動 (偶爾對話)

# - "high"           # 高互動 (頻繁問答)

# - "immersive"      # 沉浸式 (角色扮演)

```



-----



## 🌍 **語言與本地化 (Language & Localization)**



### 語言設定



```yaml

language: "en-US"                              # 主要語言



# 支援的語言代碼:

# - "en-US", "en-GB"     # 英語 (美式/英式)

# - "zh-CN", "zh-TW"     # 中文 (簡體/繁體)

# - "ja-JP"              # 日語

# - "ko-KR"              # 韓語

# - "es-ES", "es-MX"     # 西班牙語

# - "fr-FR"              # 法語

# - "de-DE"              # 德語

# - "it-IT"              # 義大利語

# - "pt-BR", "pt-PT"     # 葡萄牙語

# - "ru-RU"              # 俄語

# - "ar-SA"              # 阿拉伯語

# - "hi-IN"              # 印地語

```



### 文化適應



```yaml

cultural_context: "american"                   # 文化背景



# 文化背景選項:

# - "american", "british", "australian"

# - "chinese", "japanese", "korean"

# - "european", "latin_american"

# - "middle_eastern", "indian", "african"



localization_style: "formal"                   # 本地化風格



# 本地化風格:

# - "formal"         # 正式

# - "casual"         # 隨意

# - "traditional"    # 傳統

# - "modern"         # 現代

```



-----



## ⚙️ **技術參數 (Technical Parameters)**



### TTS 引擎選擇



```yaml

tts_provider: "elevenlabs"                     # TTS 提供商



# TTS 提供商選項:

# - "elevenlabs"     # ElevenLabs (推薦品質)

# - "openai"         # OpenAI TTS

# - "gemini"         # Google Gemini

# - "edge"           # Microsoft Edge TTS (免費)

```



### 音訊品質設定



```yaml

audio_format: "mp3"                            # 音訊格式

sample_rate: 44100                             # 取樣率

bitrate: 192                                   # 位元率 (kbps)

channels: 2                                    # 聲道數 (1=單聲道, 2=立體聲)



# 品質預設:

# 高品質: sample_rate: 48000, bitrate: 320

# 標準品質: sample_rate: 44100, bitrate: 192

# 壓縮品質: sample_rate: 22050, bitrate: 128

```



### 生成參數



```yaml

creativity_level: 0.7                          # 創意程度 (0.0-1.0)

randomness: 0.3                                # 隨機性 (0.0-1.0)

temperature: 0.8                               # LLM 溫度參數

max_tokens: 4000                               # 最大生成令牌數



# 創意程度建議:

# - 0.1-0.3: 事實性內容 (新聞、教育)

# - 0.4-0.6: 平衡內容 (商業、分析)  

# - 0.7-0.9: 創意內容 (故事、娛樂)

```



-----



## 🎯 **內容生成選項 (Content Generation Options)**



### 參與要素



```yaml

engagement_factors:                            # 參與要素

  - "questions"                                # 問題

  - "examples"                                 # 實例

  - "analogies"                                # 類比

  - "stories"                                  # 故事

  - "statistics"                               # 統計數據

  - "quotes"                                   # 引用

  - "interactive_elements"                     # 互動元素



include_timestamps: true                       # 包含時間戳

include_chapter_markers: false                 # 包含章節標記

add_background_music: false                    # 添加背景音樂

```



### 內容過濾



```yaml

content_filter:                                # 內容過濾

  profanity: false                             # 粗俗語言

  sensitive_topics: "moderate"                 # 敏感話題處理

  fact_checking: true                          # 事實檢查



# 敏感話題處理:

# - "strict"     # 嚴格過濾

# - "moderate"   # 適度過濾  

# - "lenient"    # 寬鬆過濾

# - "none"       # 不過濾

```



-----



## 📊 **輸出設定 (Output Settings)**



### 檔案設定



```yaml

output_directory: "./outputs"                  # 輸出目錄

filename_prefix: "podcast"                     # 檔名前綴

include_metadata: true                         # 包含元數據

generate_transcript: true                      # 生成逐字稿

transcript_format: "txt"                       # 逐字稿格式 (txt/srt/vtt)

```



### 批次處理



```yaml

batch_processing: false                        # 批次處理

max_concurrent_jobs: 3                         # 最大並行任務

queue_management: true                         # 佇列管理

auto_retry: true                               # 自動重試

max_retries: 3                                 # 最大重試次數

```



-----



## 🔧 **高級設定 (Advanced Settings)**



### 模型選擇



```yaml

llm_provider: "openai"                         # LLM 提供商

llm_model: "gpt-4"                             # 具體模型



# LLM 提供商選項:

# - "openai": gpt-4, gpt-3.5-turbo

# - "anthropic": claude-3-opus, claude-3-sonnet

# - "google": gemini-pro, gemini-pro-vision

# - "local": ollama, llamacpp

```



### 快取與效能



```yaml

enable_caching: true                           # 啟用快取

cache_duration: 86400                          # 快取持續時間 (秒)

parallel_processing: true                      # 並行處理

memory_optimization: "balanced"                # 記憶體優化



# 記憶體優化選項:

# - "minimal"    # 最小記憶體使用

# - "balanced"   # 平衡模式

# - "performance" # 效能優先

```



### 錯誤處理



```yaml

error_handling:                                # 錯誤處理

  on_tts_failure: "retry"                      # TTS 失敗處理

  on_llm_timeout: "continue"                   # LLM 超時處理

  fallback_voice: "alloy"                      # 備用聲音

  

# 錯誤處理選項:

# - "retry"      # 重試

# - "skip"       # 跳過

# - "continue"   # 繼續

# - "abort"      # 中止

```



-----



## 📋 **完整範例配置**



```yaml

# === 基本資訊 ===

podcast_name: "Tech Deep Dive"

podcast_tagline: "探索科技的深層奧祕"

host_intro: "歡迎來到我們的深度技術討論"

closing_remarks: "感謝收聽，我們下期再見"



# === 角色與聲音 ===

roles_person1: "技術專家主持人"

roles_person2: "好奇的開發者"

question_voice: "Alice"

answer_voice: "Brian"

tts_model: "eleven_multilingual_v2"

openai_question_voice: "alloy"

openai_answer_voice: "nova"

openai_tts_model: "tts-1-hd"



# === 內容結構 ===

dialogue_structure:

  - "技術背景介紹"

  - "核心概念解析"

  - "實際應用案例"

  - "常見問題討論"

  - "未來發展趨勢"

  - "總結與建議"



# === 長度控制 ===

word_count: 2500

max_num_chunks: 10

min_chunk_size: 800



# === 風格設定 ===

conversation_style: "technical_detailed"

tone: "informative_accessible"

pace: "moderate"

interaction_level: "high"



# === 語言設定 ===

language: "zh-CN"

cultural_context: "chinese"

localization_style: "modern"



# === 技術參數 ===

tts_provider: "elevenlabs"

audio_format: "mp3"

sample_rate: 48000

bitrate: 320

creativity_level: 0.6

randomness: 0.4

temperature: 0.7



# === 參與要素 ===

engagement_factors:

  - "questions"

  - "examples" 

  - "analogies"

  - "interactive_elements"



# === 輸出設定 ===

output_directory: "./tech_podcasts"

filename_prefix: "tech_deep_dive"

include_metadata: true

generate_transcript: true

transcript_format: "srt"



# === 高級設定 ===

llm_provider: "openai"

llm_model: "gpt-4"

enable_caching: true

parallel_processing: true

memory_optimization: "balanced"

```



-----



## 📝 **使用建議**



1. **開始簡單**: 先使用基本參數，再逐步添加高級功能

1. **測試調整**: 生成小樣本測試不同設定的效果

1. **性能平衡**: 在品質和生成速度間找到平衡點

1. **本地化**: 根據目標聽眾調整語言和文化設定

1. **監控資源**: 注意API成本和處理時間



這份完整參考涵蓋了Podcastfy所有可用的配置選項，讓你能夠精確控制播客的生成過程。

## 🎓 **語言教學配置 (Language Teaching Configuration)**

### 核心理念
全新的教學導向等級設計，讓每個等級都有明確的語言學習目標：

```yaml
language_teaching:
  enabled: true                        # 啟用語言教學功能
  teaching_spectrum:                   # 教學光譜設計
    A1: "explicit_teaching"            # 明確教學 (80% 語言 + 20% 內容)
    A2: "guided_learning"              # 引導學習 (60% 語言 + 40% 內容)  
    B1: "integrated_teaching"          # 整合教學 (40% 語言 + 60% 內容)
    B2: "occasional_tips"              # 偶爾提點 (20% 語言 + 80% 內容)
    C1: "content_focused"              # 內容聚焦 (5% 語言 + 95% 內容)
    C2: "pure_content"                 # 純內容導向 (0% 語言 + 100% 內容)
```

### 等級特定語言教學配置

#### A1 英語老師模式
```yaml
    language_teaching_elements:
      teaching_style: "explicit_instruction"        # 明確指導式教學
      focus_areas: ["vocabulary", "grammar", "pronunciation", "common_phrases"]
      teaching_markers: [
        "In English, we often say...",
        "A useful phrase here is...",
        "Notice the grammar pattern...",
        "Let me explain this expression...",
        "This is pronounced as..."
      ]
      error_correction: "gentle_modeling"           # 溫和示範式糾錯
      repetition_for_learning: "high"              # 高頻率學習重複
```

#### A2 語言引導者模式
```yaml  
    language_teaching_elements:
      teaching_style: "natural_guidance"           # 自然引導式教學
      focus_areas: ["common_expressions", "natural_usage", "everyday_phrases", "conversation_skills"]
      teaching_markers: [
        "Here's how native speakers say it...",
        "A natural way to express this is...",
        "You might also hear...",
        "This phrase is very common...",
        "People usually say..."
      ]
      error_correction: "indirect_modeling"        # 間接示範式糾錯
      repetition_for_learning: "moderate_high"     # 中高頻率學習重複
```

#### B1 對話導師模式
```yaml
    language_teaching_elements:
      teaching_style: "natural_integration"        # 自然整合式教學
      focus_areas: ["alternative_expressions", "idiomatic_usage", "natural_phrasing", "conversation_flow"]
      teaching_markers: [
        "That's a great way to put it...",
        "Another way to say this would be...",
        "Native speakers often use...",
        "There's an interesting expression...",
        "You might also hear..."
      ]
      error_correction: "conversational_recast"    # 對話式重塑糾錯
      repetition_for_learning: "moderate"          # 適度學習重複
```

### 語言教學效果範例

**A1 等級 - 明確教學導向**:
```
Host: Welcome to today's lesson! Let me teach you this useful phrase: "to get the hang of something." 
      This means to become skillful at doing something. Notice how we say "get the hang of" - 
      it's a very common English expression.

Guest: That's a great phrase to learn! In English, we often say "I'm getting the hang of it" 
       when we're improving at something. Let me give you another example...
```

**B1 等級 - 自然整合教學**:
```
Host: That's a great way to put it - we often say "it's a game-changer" when something 
      creates a significant impact.

Guest: Exactly! And speaking of which, there's a useful expression - "to turn the tide" - 
       which means to change the direction of something. Native speakers use this phrase 
       quite often in business contexts.
```

**C2 等級 - 純內容導向**:
```
Host: The fundamental dynamics at play reveal a sophisticated interplay between 
      technological advancement and societal adaptation.

Guest: What's particularly significant is the multi-layered implications this creates 
       for future policy frameworks and regulatory approaches.
```


1. **初次使用**: 設置 `enabled: true` 開啟功能
2. **模型選擇**: Pro 模型品質較佳，Flash 模型速度較快
3. **成本控制**: 標籤嵌入會增加 API 使用量，建議先小批次測試
4. **品質檢查**: 可使用開發模式逐步檢查標籤效果
5. **失敗降級**: `fallback_enabled: true` 確保系統穩定性

### 標籤效果範例

**原始腳本**:
```
<Person1> Welcome to our discussion about artificial intelligence.
<Person2> Thanks for having me. This is such an important topic.
```

**A1等級標籤嵌入**:
```
<Person1> [gentle] [conversational] Welcome to our discussion about artificial intelligence. [PAUSE=2s]
<Person2> [happy] [supportive] Thanks for having me. [PAUSE=1s] This is such an important topic. [thoughtful]
```

**C2等級標籤嵌入**:
```
<Person1> [professional] [authoritative] Welcome to our discussion about artificial intelligence. <prosody rate="medium"> A field that's reshaping our world </prosody>
<Person2> [analytical] [sophisticated] Thanks for having me. [brief pause] This is such an important topic [insightful] that demands our careful consideration.
```
