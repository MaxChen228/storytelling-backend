#!/usr/bin/env python3
"""
Podcastfy 多模態輸入示範
展示如何處理不同類型的內容來源
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Podcastfy imports
try:
    from podcastfy.client import generate_podcast
except ImportError:
    print("❌ 需要安裝 podcastfy 套件")
    print("請執行: pip install podcastfy")
    sys.exit(1)

# Load environment variables
load_dotenv()

def example_text_input():
    """示例 1: 文本內容輸入"""
    print("\n📄 示例 1: 文本內容輸入")
    print("-" * 40)
    
    # 直接文本內容
    text_content = """
    人工智慧在教育領域的應用
    
    人工智慧正在以前所未有的方式革命教育。從個人化學習路徑到智能輔導系統，
    AI 幫助學生按照自己的節奏學習。教師可以使用 AI 工具識別學習差距並提供
    有針對性的支持。該技術還為有障礙的學生提供無障礙教育，打破傳統的學習障礙。
    """
    
    # Podcastfy 處理文本
    conversation_config = {
        "word_count": 300,
        "conversation_style": ["engaging", "educational"],
        "language": "English", 
        "dialogue_structure": "two_speakers",
        "roles": ["Host", "Expert"],
        "output_folder": "./multimodal_examples/text_example"
    }
    
    try:
        result = generate_podcast(
            text=text_content,
            llm_model_name="gemini-2.5-pro",
            api_key_label="GEMINI_API_KEY",
            conversation_config=conversation_config,
            tts_model="gemini"
        )
        print(f"✅ 文本處理成功: {result}")
    except Exception as e:
        print(f"❌ 文本處理失敗: {e}")


def example_file_input():
    """示例 2: 檔案輸入"""
    print("\n📁 示例 2: 檔案輸入")
    print("-" * 40)
    
    # 檢查測試檔案
    test_file = "./sample_article.txt"
    if not Path(test_file).exists():
        print(f"❌ 測試檔案不存在: {test_file}")
        return
    
    conversation_config = {
        "word_count": 400,
        "conversation_style": ["informative", "accessible"],
        "language": "English",
        "dialogue_structure": "two_speakers", 
        "roles": ["Teacher", "Student"],
        "output_folder": "./multimodal_examples/file_example"
    }
    
    try:
        # 讀取檔案內容
        with open(test_file, 'r', encoding='utf-8') as f:
            file_content = f.read()
            
        result = generate_podcast(
            text=file_content,
            llm_model_name="gemini-2.5-pro",
            api_key_label="GEMINI_API_KEY", 
            conversation_config=conversation_config,
            tts_model="gemini"
        )
        print(f"✅ 檔案處理成功: {result}")
    except Exception as e:
        print(f"❌ 檔案處理失敗: {e}")


def example_pdf_input():
    """示例 3: PDF 檔案輸入"""
    print("\n📋 示例 3: PDF 檔案輸入")
    print("-" * 40)
    
    # 這裡示範 PDF 處理的方式
    pdf_path = "./sample_document.pdf"  # 您需要提供 PDF 檔案
    
    conversation_config = {
        "word_count": 500,
        "conversation_style": ["analytical", "detailed"],
        "language": "English",
        "dialogue_structure": "two_speakers",
        "roles": ["Analyst", "Researcher"], 
        "output_folder": "./multimodal_examples/pdf_example"
    }
    
    if Path(pdf_path).exists():
        try:
            result = generate_podcast(
                pdf_file_path=pdf_path,
                llm_model_name="gemini-2.5-pro",
                api_key_label="GEMINI_API_KEY",
                conversation_config=conversation_config,
                tts_model="gemini"
            )
            print(f"✅ PDF 處理成功: {result}")
        except Exception as e:
            print(f"❌ PDF 處理失敗: {e}")
    else:
        print(f"⚠️  PDF 檔案不存在: {pdf_path}")
        print("   請提供 PDF 檔案進行測試")


def example_url_input():
    """示例 4: 網頁 URL 輸入"""
    print("\n🌐 示例 4: 網頁 URL 輸入")
    print("-" * 40)
    
    # 示範網頁處理
    urls = [
        "https://blog.google/technology/ai/google-ai-overview-io-2024/",  # Google AI 新聞
        # "https://openai.com/index/gpt-4o/",  # 技術文章示例
    ]
    
    conversation_config = {
        "word_count": 400,
        "conversation_style": ["current", "technical"],
        "language": "English",
        "dialogue_structure": "two_speakers",
        "roles": ["News Anchor", "Tech Expert"],
        "output_folder": "./multimodal_examples/url_example"
    }
    
    try:
        result = generate_podcast(
            urls=urls,
            llm_model_name="gemini-2.5-pro", 
            api_key_label="GEMINI_API_KEY",
            conversation_config=conversation_config,
            tts_model="gemini"
        )
        print(f"✅ 網頁處理成功: {result}")
    except Exception as e:
        print(f"❌ 網頁處理失敗: {e}")


def example_youtube_input():
    """示例 5: YouTube 影片輸入"""
    print("\n🎥 示例 5: YouTube 影片輸入")
    print("-" * 40)
    
    # YouTube 影片連結
    youtube_urls = [
        "https://www.youtube.com/watch?v=EXAMPLE_ID",  # 請替換為實際連結
    ]
    
    conversation_config = {
        "word_count": 600,
        "conversation_style": ["video_summary", "engaging"],
        "language": "English",
        "dialogue_structure": "two_speakers",
        "roles": ["Host", "Video Analyst"],
        "output_folder": "./multimodal_examples/youtube_example"
    }
    
    print("⚠️  YouTube 處理需要實際的影片連結")
    print("   請提供有效的 YouTube URL 進行測試")
    
    # 取消註解以下代碼來測試實際的 YouTube 連結
    """
    try:
        result = generate_podcast(
            youtube_urls=youtube_urls,
            llm_model_name="gemini-2.5-pro",
            api_key_label="GEMINI_API_KEY",
            conversation_config=conversation_config,
            tts_model="gemini"
        )
        print(f"✅ YouTube 處理成功: {result}")
    except Exception as e:
        print(f"❌ YouTube 處理失敗: {e}")
    """


def example_multiple_sources():
    """示例 6: 多重來源整合"""
    print("\n📚 示例 6: 多重來源整合")
    print("-" * 40)
    
    # 可以組合多個 URL
    multiple_urls = [
        "https://ai.google.dev/gemini-api/docs/audio",
        "https://ai.google.dev/gemini-api/docs/models",
    ]
    
    conversation_config = {
        "word_count": 700,
        "conversation_style": ["comprehensive", "technical"],
        "language": "English", 
        "dialogue_structure": "two_speakers",
        "roles": ["Tech Journalist", "API Expert"],
        "custom_instructions": """
            Synthesize information from multiple sources.
            Compare and contrast different aspects.
            Provide practical implementation insights.
        """,
        "output_folder": "./multimodal_examples/multiple_sources"
    }
    
    try:
        result = generate_podcast(
            urls=multiple_urls,
            llm_model_name="gemini-2.5-pro",
            api_key_label="GEMINI_API_KEY", 
            conversation_config=conversation_config,
            tts_model="gemini"
        )
        print(f"✅ 多重來源處理成功: {result}")
    except Exception as e:
        print(f"❌ 多重來源處理失敗: {e}")


def show_multimodal_capabilities():
    """展示 Podcastfy 多模態功能概覽"""
    print("=" * 60)
    print("🔍 Podcastfy 多模態輸入功能概覽")
    print("=" * 60)
    
    capabilities = {
        "📄 文本內容": {
            "方法": "generate_podcast(text=content)",
            "適用": "直接文本、文章內容、腳本",
            "優勢": "最直接、處理速度快"
        },
        "📁 檔案輸入": {
            "方法": "generate_podcast(text=file_content)", 
            "適用": ".txt, .md 等文本檔案",
            "優勢": "支援大型文檔、自動編碼處理"
        },
        "📋 PDF 文檔": {
            "方法": "generate_podcast(pdf_file_path=path)",
            "適用": "學術論文、報告、電子書",
            "優勢": "自動文本提取、格式處理"
        },
        "🌐 網頁內容": {
            "方法": "generate_podcast(urls=[url1, url2])",
            "適用": "新聞文章、部落格、文檔網站",
            "優勢": "即時內容、多頁面整合"
        },
        "🎥 YouTube 影片": {
            "方法": "generate_podcast(youtube_urls=[url])",
            "適用": "教育影片、演講、訪談",
            "優勢": "自動字幕提取、影片摘要"
        },
        "📚 多重來源": {
            "方法": "generate_podcast(urls=[multiple_urls])",
            "適用": "研究主題、比較分析", 
            "優勢": "綜合多個觀點、全面性分析"
        }
    }
    
    for input_type, details in capabilities.items():
        print(f"\n{input_type}")
        print(f"   方法: {details['方法']}")
        print(f"   適用: {details['適用']}")
        print(f"   優勢: {details['優勢']}")
    
    print("\n" + "=" * 60)
    print("💡 使用建議")
    print("=" * 60)
    print("1. PDF: 適合處理學術內容和長篇文檔")
    print("2. URL: 適合即時新聞和網路文章")  
    print("3. YouTube: 適合影片內容摘要和教育材料")
    print("4. 多重來源: 適合研究性主題和比較分析")


if __name__ == "__main__":
    print("🎯 Podcastfy 多模態輸入示範")
    
    # 顯示功能概覽
    show_multimodal_capabilities()
    
    print("\n" + "=" * 60)
    print("🧪 示例測試")
    print("=" * 60)
    
    # 創建示例輸出目錄
    Path("./multimodal_examples").mkdir(exist_ok=True)
    
    # 執行示例（根據可用資源）
    example_text_input()        # 文本處理
    example_file_input()        # 檔案處理
    example_pdf_input()         # PDF 處理
    example_url_input()         # 網頁處理
    example_youtube_input()     # YouTube 處理
    example_multiple_sources()  # 多重來源
    
    print("\n" + "=" * 60)
    print("✅ 多模態示例展示完成")
    print("=" * 60)
    print("\n💡 實際使用時，請確保：")
    print("1. API 配額充足")
    print("2. 網路連線穩定")
    print("3. 輸入內容格式正確")
    print("4. 輸出目錄有寫入權限")