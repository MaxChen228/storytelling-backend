# LLM標籤嵌入系統實施計劃

## 📋 專案概述

### 目標
將現有的二步驟播客生成流程升級為三步驟智能化流程：
1. **Step 1**: Podcastfy 生成腳本 (現有)
2. **Step 2**: LLM 智能嵌入標籤 (新增)
3. **Step 3**: Gemini TTS 生成音頻 (修改)

### 核心價值
- 使用 LLM 模型智能分析對話內容，自動嵌入適當的 SSML 和情感標籤
- 根據英語等級配置提供風格參數，讓 LLM 自適應調整標籤策略
- 提升 TTS 生成音頻的表現力和自然度

---

## 🏗️ 當前系統架構分析

### 現有檔案結構
```
podcastfy_test/
├── generate_script.py      # Step 1: 腳本生成
├── generate_audio.py       # Step 2: 音頻生成
├── podcast_workflow.py     # 工作流程控制器
├── podcast_config.yaml     # 統一配置文件
└── output/
    ├── scripts/            # 腳本輸出目錄
    └── audio/              # 音頻輸出目錄
```

### 當前工作流程
1. `generate_script.py` → 使用 Podcastfy 生成結構化對話腳本
2. `generate_audio.py` → 使用 Gemini Multi-Speaker TTS 直接從腳本生成音頻

### 現有配置系統
- **六等級英語設計**: A1(探索者) → C2(大師)
- **統一配置文件**: 包含風格、聲線、語速、概念處理等完整配置
- **專業結構化**: 已實現 engagement_factors, concept_processing, repetition_strategy 等

---

## 🎭 Gemini TTS 標籤系統分析

### 已確認支援的標籤

#### 情感標籤 ✅
```
[happy] [sad] [angry] [excited] [calm] [nervous] 
[whisper] [shout] [furious] [gentle] [dramatic] [bored]
```

#### 語音效果標籤 ✅
```
[laughing] [sighing] [crying] [coughing] [yawning] 
[gasping] [sniffing] [breathing]
```

#### SSML 標籤 (部分支援)
```xml
<break time="2s"/>              <!-- 暫停控制 ✅ -->
<prosody rate="slow">           <!-- 語速控制 ✅ -->
<prosody pitch="high">          <!-- 音調控制 ✅ -->
<prosody volume="loud">         <!-- 音量控制 ✅ -->
<say-as interpret-as="date">    <!-- 內容格式 ⚠️ 部分支援 -->
```

#### 語音風格控制 ✅
```
[conversational] [professional] [storytelling] 
[narrator] [robotic] [childlike]
```

### 限制與最佳實踐
- 避免長段落中過多標籤（可能被朗讀出來）
- 優先使用情感標籤，比 SSML 更自然
- 可混合使用：`[sad] <break time="1s"/> 內容 <prosody rate="slow">慢速</prosody>`

---

## 🚀 新系統設計方案

### Step 2: 智能標籤嵌入系統

#### 主要檔案: `embed_tags.py`

```python
# 核心功能設計概念
class TagEmbeddingEngine:
    def __init__(self, config, english_level):
        # 載入等級配置和標籤策略
        
    def analyze_dialogue_context(self, script_content):
        # LLM 分析對話內容，識別情境和情緒
        
    def generate_tag_embedding_prompt(self, level_config):
        # 根據等級配置生成 LLM 提示
        
    def embed_tags_with_llm(self, script_content, style_params):
        # 調用 LLM 進行智能標籤嵌入
        
    def post_process_tags(self, tagged_script):
        # 後處理：驗證標籤格式，修正錯誤
```

#### LLM 提示模板系統

**A1等級範例提示**:
```
你是專業的播客製作助理。請為以下腳本嵌入適當的語音標籤：

風格參數：
- 對話風格: gentle, wondering, patient, supportive, exploratory
- 語速: slow
- 情感密度: low
- 標籤使用策略: 溫和情感 + 充分暫停

請在適當位置嵌入：
1. 情感標籤: [gentle], [curious], [supportive]
2. 暫停標籤: [PAUSE=2s] (段落間), [PAUSE=1s] (句子間)
3. 語調控制: <prosody rate="slow"> 用於重點說明

原始腳本：
{script_content}

輸出帶標籤的腳本：
```

**B1等級範例提示**:
```
根據討論者風格嵌入標籤：
- 對話風格: balanced, engaging, mixed complexity
- 標籤密度: moderate
- 重點：[thoughtful], [engaged], [PAUSE=1s], <prosody> 變化
```

**C2等級範例提示**:
```
專業論述風格標籤嵌入：
- 豐富情感表達: [analytical], [insightful], [professional]
- 語調變化: 頻繁使用 <prosody> 調節
- 精確暫停控制
```

### 配置文件擴展

#### `podcast_config.yaml` 新增區塊
```yaml
# 新增標籤嵌入配置
tag_embedding:
  enabled: true
  llm_model: "gemini-2.0-flash-exp"  # 或 gpt-4
  
# 在每個等級配置中添加
level_configs:
  A1:
    # ... 現有配置 ...
    tag_embedding:
      density: "low"                    # 標籤使用密度
      emotion_range: ["gentle", "curious", "supportive"]
      pause_frequency: "high"           # 暫停頻率
      prosody_usage: "minimal"          # 語調變化使用程度
      primary_style: "[conversational]"
      
  B1:
    tag_embedding:
      density: "moderate"
      emotion_range: ["thoughtful", "engaged", "balanced"]
      pause_frequency: "moderate"
      prosody_usage: "selective"
      primary_style: "[conversational]"
      
  C2:
    tag_embedding:
      density: "high"
      emotion_range: ["analytical", "insightful", "professional", "sophisticated"]
      pause_frequency: "strategic"
      prosody_usage: "rich"
      primary_style: "[professional]"
```

### 工作流程整合

#### 更新 `podcast_workflow.py`
```python
def run_step2_embed_tags(self, script_dir: str) -> Optional[str]:
    """執行步驟2：LLM智能嵌入標籤"""
    print("\n🚀 步驟 2: LLM 智能標籤嵌入")
    
    # 調用標籤嵌入引擎
    from embed_tags import embed_tags_with_llm
    
    tagged_script_dir = embed_tags_with_llm(script_dir)
    if tagged_script_dir:
        return tagged_script_dir
    else:
        print("❌ 標籤嵌入失敗")
        return None
```

#### 修改三種模式
- **開發模式**: Script → 確認 → Tags → 確認 → Audio
- **生產模式**: Script → Tags → Audio (自動)
- **自訂模式**: 可選擇跳過標籤嵌入步驟

---

## 🎯 實施步驟

### Phase 1: 核心引擎開發
1. 創建 `embed_tags.py` 主要功能
2. 實現 LLM 提示生成系統
3. 建立標籤驗證和後處理邏輯

### Phase 2: 配置整合
1. 擴展 `podcast_config.yaml` 標籤配置
2. 為六個等級設計專屬標籤策略
3. 實現風格參數到提示的映射

### Phase 3: 工作流程升級
1. 更新 `podcast_workflow.py` 三步驟邏輯
2. 修改 `generate_audio.py` 支援標籤腳本
3. 確保向後兼容性

### Phase 4: 測試與優化
1. 測試各等級標籤嵌入效果
2. 調優 LLM 提示模板
3. 驗證 TTS 音頻品質提升

---

## 🔧 技術實作細節

### LLM 標籤嵌入流程
1. **讀取配置**: 獲取當前等級的標籤策略參數
2. **生成提示**: 根據風格參數構建 LLM 提示
3. **內容分析**: LLM 分析腳本情境和情緒
4. **標籤嵌入**: 智能選擇並嵌入適當標籤
5. **後處理**: 驗證標籤格式，確保 TTS 相容性
6. **保存結果**: 輸出帶標籤腳本到新目錄

### 目錄結構調整
```
output/
├── scripts/
│   └── script_20250821_HHMMSS/
│       ├── podcast_script.txt          # 原始腳本
│       └── metadata.json
├── tagged_scripts/                     # 新增
│   └── tagged_20250821_HHMMSS/
│       ├── podcast_script_tagged.txt   # 帶標籤腳本
│       ├── tag_metadata.json          # 標籤使用統計
│       └── original_script.txt        # 原始腳本備份
└── audio/
    └── audio_20250821_HHMMSS/
        ├── podcast.wav
        └── metadata.json
```

### 預期效果範例

**原始腳本**:
```
<Person1> "Welcome to Natural Conversations - 探索者"
<Person2> "It's wonderful to be back, exploring these fascinating shifts"
```

**A1等級標籤嵌入後**:
```
<Person1> "[gentle] [conversational] Welcome to Natural Conversations - 探索者 [PAUSE=2s]"
<Person2> "[happy] [warm] It's wonderful to be back, [PAUSE=1s] exploring these fascinating shifts [gentle]"
```

**C2等級標籤嵌入後**:
```
<Person1> "[professional] [confident] Welcome to Natural Conversations - 探索者 <prosody rate=\"medium\"> where intellectual discourse meets analytical depth </prosody>"
<Person2> "[analytical] [sophisticated] It's wonderful to be back, [thoughtful] <prosody pitch=\"high\"> exploring these fascinating paradigm shifts </prosody> [insightful]"
```

---

## 🎯 下一步執行指引

### 立即行動項目
1. **創建 `embed_tags.py`** - 實現 LLM 驅動的標籤嵌入引擎
2. **擴展配置文件** - 為所有等級添加 `tag_embedding` 配置區塊  
3. **更新工作流程** - 整合三步驟流程到 `podcast_workflow.py`
4. **修改音頻生成** - 讓 `generate_audio.py` 支援帶標籤腳本

### 關鍵技術決策
- **LLM 模型選擇**: 建議使用 `gemini-2.0-flash-exp` 或 `gpt-4o-mini`
- **API 整合**: 複用現有的 Gemini API 配置或添加 OpenAI 支援
- **錯誤處理**: 如標籤嵌入失敗，自動降級為原始腳本
- **性能優化**: 支援腳本分段處理，避免 token 限制

### 測試策略
1. 使用現有腳本測試標籤嵌入效果
2. 對比標籤前後的 TTS 音頻品質
3. 驗證六個等級的標籤策略差異
4. 確保向後兼容性

---

## 📂 現有資源清單

### 可用腳本樣本
- `output/scripts/script_20250821_105724/` - A1等級 "探索者" 風格
- `output/scripts/script_20250821_103729/` - B1等級 "討論者" 風格

### 配置文件狀態
- ✅ `podcast_config.yaml` - 完整的六等級配置系統
- ✅ 概念拆解與重複機制已實現
- ✅ 專業結構化配置已就緒
- ⭕ 需要添加 `tag_embedding` 配置區塊

### 技術環境
- ✅ Podcastfy 框架已配置
- ✅ Gemini API 已設置 (GEMINI_API_KEY)
- ✅ Python 環境與依賴已就緒
- ⭕ 需要確認 LLM API 配置

---

## 🔄 實施順序建議

### 第一優先級 (核心功能)
1. **創建 `embed_tags.py`**
   - 實現 `TagEmbeddingEngine` 類別
   - 建立 LLM 提示生成系統
   - 實現標籤嵌入和後處理邏輯

### 第二優先級 (配置整合)
2. **擴展 `podcast_config.yaml`**
   - 為所有六個等級添加 `tag_embedding` 配置
   - 定義等級特定的標籤策略
   - 設置全域標籤嵌入參數

### 第三優先級 (工作流程整合)
3. **更新 `podcast_workflow.py`**
   - 新增 `run_step2_embed_tags()` 方法
   - 修改三種模式以支援三步驟流程
   - 實現步驟間的錯誤處理和降級

4. **修改 `generate_audio.py`**
   - 支援讀取帶標籤腳本
   - 保持對原始腳本的向後兼容
   - 更新元數據記錄標籤使用情況

### 第四優先級 (測試與優化)
5. **測試與驗證**
   - 使用現有腳本測試標籤嵌入
   - 對比音頻品質改善效果
   - 調優各等級的提示模板

---

## 💡 關鍵設計原則

### 1. 智能化優先
- 讓 LLM 根據上下文智能選擇標籤，而非硬編碼規則
- 提供風格參數指導，但保持 LLM 的創造性

### 2. 等級適配
- A1/A2: 基礎標籤，溫和情感，充分暫停
- B1/B2: 平衡使用，自然節奏
- C1/C2: 豐富表達，專業語調控制

### 3. 向後兼容
- 原有二步驟流程仍可正常運作
- 標籤嵌入失敗時自動降級為原始腳本
- 保持現有配置文件結構

### 4. 可配置性
- 可開關標籤嵌入功能
- 可調整標籤密度和策略
- 支援自訂 LLM 模型選擇

---

## 🎯 預期成果

### 音頻品質提升
- 更自然的對話節奏和情感表達
- 適合不同英語等級的語音風格
- 增強的故事性和參與度

### 系統功能性
- 完整的三步驟工作流程
- 靈活的配置和自訂選項  
- 強健的錯誤處理和降級機制

### 開發體驗
- 清晰的步驟分離和確認機制
- 詳細的標籤使用統計和分析
- 易於調試和優化的模組化設計

---

## 📞 交接說明

此文檔包含了實施 LLM 標籤嵌入系統的完整計劃。下一個 agent 可以：

1. **從 Phase 1 開始實施** - 創建 `embed_tags.py` 核心引擎
2. **參考現有腳本樣本** - 瞭解腳本格式和內容風格
3. **遵循等級配置邏輯** - 確保標籤策略符合既有的六等級設計
4. **保持系統一致性** - 延續現有的配置文件結構和工作流程模式

### 重要提醒
- 請確保在虛擬環境中工作：`source ../.venvs/storytelling/bin/activate`（第一次可執行 `bash ../scripts/bootstrap_venv.sh storytelling`）
- 測試時可使用現有的腳本樣本進行驗證
- 保持與現有 Gemini API 配置的一致性
- 遵循專案的 commit 命名慣例

---

*📅 計劃創建時間: 2025-08-21*  
*🎯 預期完成時間: 1-2天*  
*👤 負責 Agent: 下一個接手的 Claude Code Agent*
