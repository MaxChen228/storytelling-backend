# 🎯 Podcastfy 多模態輸入完整指南

## 📋 概述

Podcastfy 支援多種輸入格式，讓您可以從任何類型的內容生成播客。以下是詳細的使用方法和最佳實踐。

## 🔍 支援的輸入格式

### 1. 📄 文本內容輸入

**最直接的方式 - 適合已準備好的文本內容**

```python
from podcastfy.client import generate_podcast

# 方式 A: 直接文本字串
text_content = """
您的文章內容...
可以是任何語言的文本
支援 Markdown 格式
"""

result = generate_podcast(
    text=text_content,
    llm_model_name="gemini-2.5-pro",
    api_key_label="GEMINI_API_KEY",
    conversation_config={
        "word_count": 500,
        "language": "English",
        "dialogue_structure": "two_speakers"
    }
)

# 方式 B: 從檔案讀取
with open("article.txt", "r", encoding="utf-8") as f:
    file_content = f.read()
    
result = generate_podcast(text=file_content, ...)
```

### 2. 📋 PDF 文檔輸入

**自動解析 PDF - 適合學術論文、報告、電子書**

```python
# PDF 檔案會自動解析文本內容
result = generate_podcast(
    pdf_file_path="./document.pdf",
    llm_model_name="gemini-2.5-pro",
    api_key_label="GEMINI_API_KEY",
    conversation_config={
        "word_count": 800,
        "conversation_style": ["academic", "detailed"],
        "roles": ["Researcher", "Professor"]
    }
)
```

**PDF 處理特色：**
- ✅ 自動文本提取
- ✅ 保留文檔結構
- ✅ 處理表格和圖表描述
- ✅ 支援多頁面文檔

### 3. 🌐 網頁內容輸入

**即時網頁抓取 - 適合新聞、部落格、線上文章**

```python
# 單一網頁
result = generate_podcast(
    urls=["https://example.com/article"],
    llm_model_name="gemini-2.5-pro", 
    api_key_label="GEMINI_API_KEY",
    conversation_config={
        "word_count": 600,
        "conversation_style": ["news", "current"],
        "roles": ["News Anchor", "Reporter"]
    }
)

# 多個網頁整合
result = generate_podcast(
    urls=[
        "https://site1.com/article1",
        "https://site2.com/article2",
        "https://site3.com/article3"
    ],
    conversation_config={
        "word_count": 1000,
        "custom_instructions": "Compare and synthesize information from all sources"
    }
)
```

**網頁處理特色：**
- ✅ 自動內容擷取
- ✅ 移除廣告和導航
- ✅ 多頁面內容整合  
- ✅ 即時更新內容

### 4. 🎥 YouTube 影片輸入

**影片轉錄分析 - 適合教育影片、演講、訪談**

```python
# 單一 YouTube 影片
result = generate_podcast(
    youtube_urls=["https://youtube.com/watch?v=VIDEO_ID"],
    llm_model_name="gemini-2.5-pro",
    api_key_label="GEMINI_API_KEY", 
    conversation_config={
        "word_count": 700,
        "conversation_style": ["video_summary", "engaging"],
        "roles": ["Host", "Video Analyst"],
        "custom_instructions": "Summarize key points and provide additional context"
    }
)

# 多個影片系列分析
result = generate_podcast(
    youtube_urls=[
        "https://youtube.com/watch?v=VIDEO1",
        "https://youtube.com/watch?v=VIDEO2"
    ],
    conversation_config={
        "custom_instructions": "Compare themes across videos and identify patterns"
    }
)
```

**YouTube 處理特色：**
- ✅ 自動字幕提取
- ✅ 影片摘要生成
- ✅ 關鍵重點識別
- ✅ 多影片主題整合

## 🛠️ 進階多模態技巧

### 組合不同來源

```python
# 組合 PDF + 網頁內容（需分別處理後整合）

# Step 1: 處理 PDF
pdf_result = generate_podcast(
    pdf_file_path="research_paper.pdf",
    conversation_config={"word_count": 400}
)

# Step 2: 處理相關網頁
web_result = generate_podcast(
    urls=["https://related-article.com"],
    conversation_config={"word_count": 300}
)

# Step 3: 手動整合（或創建綜合腳本）
```

### 內容預處理

```python
def preprocess_content(input_path, input_type):
    """預處理不同類型的輸入"""
    
    if input_type == "text":
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # 清理文本、移除多餘空白等
        return content.strip()
    
    elif input_type == "pdf": 
        # PDF 由 Podcastfy 自動處理
        return input_path
    
    elif input_type == "url":
        # URL 由 Podcastfy 自動抓取
        return [input_path]
    
    elif input_type == "youtube":
        # YouTube 由 Podcastfy 自動轉錄
        return [input_path]
```

## 🎛️ 配置最佳化

### 根據內容類型調整配置

```python
# 學術 PDF 配置
academic_config = {
    "word_count": 800,
    "conversation_style": ["academic", "detailed", "analytical"],
    "roles": ["Professor", "Graduate Student"],
    "custom_instructions": "Explain complex concepts in accessible terms"
}

# 新聞網頁配置  
news_config = {
    "word_count": 400,
    "conversation_style": ["current", "engaging", "factual"],
    "roles": ["News Anchor", "Correspondent"],
    "custom_instructions": "Focus on latest developments and implications"
}

# YouTube 教育影片配置
video_config = {
    "word_count": 600,
    "conversation_style": ["educational", "engaging"],
    "roles": ["Host", "Subject Expert"],
    "custom_instructions": "Summarize key learning points and add context"
}
```

## 📊 輸入限制與最佳實踐

### 內容長度限制

| 輸入類型 | 建議長度 | 最大長度 | 處理時間 |
|----------|----------|----------|----------|
| 📄 文本 | 5,000 字符 | 50,000 字符 | 快速 |
| 📋 PDF | 20 頁 | 100 頁 | 中等 |
| 🌐 網頁 | 5 篇文章 | 10 篇文章 | 中等 |
| 🎥 YouTube | 30 分鐘 | 2 小時 | 較慢 |

### 品質優化建議

**1. 內容選擇**
- ✅ 選擇結構清晰的內容
- ✅ 避免過於技術性的術語（除非目標是高級聽眾）
- ✅ 確保內容有足夠的信息密度

**2. 配置調整**
- ✅ 根據內容難度調整 `english_level`
- ✅ 根據內容豐富度調整 `word_count`
- ✅ 選擇合適的對話角色（roles）

**3. 錯誤處理**
- ✅ 檢查輸入檔案存在
- ✅ 驗證 URL 可訪問性
- ✅ 確認 YouTube 影片為公開狀態

## 🔧 實際使用範例

### 範例 1: 處理學術論文

```python
from integrated_podcast_generator import IntegratedPodcastGenerator, IntegratedPodcastConfig

# 學術 PDF 轉播客
config = IntegratedPodcastConfig(
    input_source="./research_paper.pdf",
    input_type="pdf",
    english_level="C1",  # 高級英語
    target_minutes=8,
    style_instructions="academic but accessible, explain technical terms",
    host_voice="Charon",    # 知識型語音
    expert_voice="Kore"     # 權威語音
)

generator = IntegratedPodcastGenerator()
result = generator.generate(config)
```

### 範例 2: 新聞文章整合

```python
# 多個新聞來源整合
config = IntegratedPodcastConfig(
    input_source="https://techcrunch.com/2024/ai-developments/",
    input_type="url", 
    english_level="B2",
    target_minutes=5,
    style_instructions="current events, engaging discussion",
    host_voice="Aoede",     # 輕快主持
    expert_voice="Puck"     # 活潑分析
)
```

### 範例 3: YouTube 教育內容

```python
# YouTube 教育影片摘要
config = IntegratedPodcastConfig(
    input_source="https://youtube.com/watch?v=EDUCATION_VIDEO",
    input_type="youtube",
    english_level="B1", 
    target_minutes=6,
    style_instructions="educational summary, highlight key concepts",
    host_voice="Kore",      # 清晰教學
    expert_voice="Leda"     # 年輕學習者
)
```

## 💡 多模態整合策略

### 內容分層處理

1. **基礎層**: 使用 PDF/文本建立核心知識
2. **更新層**: 使用網頁獲取最新信息  
3. **視覺層**: 使用 YouTube 補充視覺說明
4. **整合層**: 綜合所有來源生成全面播客

### 自動化工作流程

```python
def smart_multimodal_processor(sources):
    """智能多模態處理器"""
    
    results = []
    
    for source in sources:
        # 自動檢測類型
        if source.endswith('.pdf'):
            input_type = 'pdf'
        elif source.startswith('http') and 'youtube' in source:
            input_type = 'youtube'
        elif source.startswith('http'):
            input_type = 'url'
        else:
            input_type = 'text'
        
        # 根據類型調整配置
        config = adjust_config_by_type(input_type)
        
        # 處理內容
        result = process_with_podcastfy(source, config)
        results.append(result)
    
    return integrate_results(results)
```

## 🎉 總結

Podcastfy 的多模態功能讓您可以：

✅ **PDF 文檔**: 學術論文 → 教育播客  
✅ **網頁文章**: 即時新聞 → 新聞播客  
✅ **YouTube 影片**: 教學影片 → 摘要播客  
✅ **多重來源**: 研究主題 → 綜合分析播客

**核心優勢：**
- 🚀 自動內容提取和清理
- 🎯 智能結構化處理  
- 🔄 統一的 API 介面
- 📈 可擴展的處理流程

現在您的工作流程可以處理任何類型的內容，從簡單文本到複雜的多媒體資源，全部整合到統一的播客生成管道中！