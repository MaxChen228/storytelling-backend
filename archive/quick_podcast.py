#!/usr/bin/env python3
"""
快速播客生成器
簡單命令行界面，可調整等級、文章、篇幅
使用方式：python quick_podcast.py
"""

import os
import sys
import yaml
from pathlib import Path
from integrated_podcast_generator import generate_from_config, IntegratedPodcastConfig


def create_quick_config(level: str, article: str, minutes: int, output_dir: str = "./podcast_output", 
                        host_voice: str = "Kore", expert_voice: str = "Puck"):
    """快速創建配置"""
    config_data = {
        'basic': {
            'english_level': level,
            'target_minutes': minutes,
            'style_instructions': 'conversational, engaging, educational'
        },
        'input': {
            'source': article,
            'type': 'auto'
        },
        'voices': {
            'host_voice': host_voice,
            'expert_voice': expert_voice
        },
        'advanced': {
            'use_podcastfy_tts': False,  # 使用 Gemini Multi-Speaker TTS
            'output_dir': output_dir,
            'llm_model': 'gemini-2.5-flash',
            'tts_model': 'gemini-2.5-flash-preview-tts'
        }
    }
    
    # 保存到臨時配置
    config_path = "./temp_config.yaml"
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
    
    return config_path


def interactive_setup():
    """互動式設定"""
    print("🎯 快速播客生成器")
    print("=" * 50)
    
    # 1. 英語等級
    print("\n📊 選擇英語等級 (CEFR):")
    levels = {
        '1': 'A1 - 初學者（基礎詞彙）',
        '2': 'A2 - 初級（日常話題）', 
        '3': 'B1 - 中級（工作學習話題）',
        '4': 'B2 - 中上級（抽象概念）',
        '5': 'C1 - 高級（專業內容）',
        '6': 'C2 - 精通（母語水準）'
    }
    
    for key, desc in levels.items():
        print(f"  {key}. {desc}")
    
    level_choice = input("\n選擇等級 (1-6) [預設: 4-B2]: ").strip() or '4'
    level_map = {'1': 'A1', '2': 'A2', '3': 'B1', '4': 'B2', '5': 'C1', '6': 'C2'}
    level = level_map.get(level_choice, 'B2')
    
    # 2. 文章來源
    print(f"\n📄 輸入文章來源:")
    print("  支援格式：")
    print("  • 文本檔案: ./article.txt")
    print("  • PDF 文檔: ./document.pdf") 
    print("  • 網頁連結: https://example.com/article")
    print("  • YouTube: https://youtube.com/watch?v=...")
    
    article = input(f"\n文章來源 [預設: ./sample_article.txt]: ").strip() or "./sample_article.txt"
    
    # 3. 篇幅
    print(f"\n⏱️ 設定播客長度:")
    print("  建議：1-2分鐘（快速），3-5分鐘（深入），5-10分鐘（完整）")
    
    minutes_input = input(f"\n目標分鐘數 [預設: 2]: ").strip() or '2'
    try:
        minutes = int(minutes_input)
    except ValueError:
        minutes = 2
    
    # 4. 輸出目錄
    output_dir = input(f"\n📁 輸出目錄 [預設: ./podcast_output]: ").strip() or "./podcast_output"
    
    return level, article, minutes, output_dir


def main():
    """主程序"""
    try:
        # 檢查是否有命令行參數
        if len(sys.argv) > 1:
            # 命令行模式
            if len(sys.argv) >= 4:
                level = sys.argv[1].upper()
                article = sys.argv[2]
                minutes = int(sys.argv[3])
                output_dir = sys.argv[4] if len(sys.argv) > 4 else "./podcast_output"
                host_voice = sys.argv[5] if len(sys.argv) > 5 else "Kore"
                expert_voice = sys.argv[6] if len(sys.argv) > 6 else "Puck"
            else:
                print("使用方式: python quick_podcast.py <等級> <文章> <分鐘數> [輸出目錄] [主持人聲線] [專家聲線]")
                print("範例: python quick_podcast.py B2 ./sample_article.txt 2")
                print("聲線範例: python quick_podcast.py B2 ./sample_article.txt 2 ./output Aoede Charon")
                print("")
                print("可用聲線: Kore（溫和女聲）, Puck（活潑男聲）, Charon（沈穩男聲）, Fenrir（專業男聲）, Aoede（優雅女聲）")
                return False
        else:
            # 從配置文件讀取設定
            config_file = Path("./podcast_config.yaml")
            if config_file.exists():
                print("🎯 從 podcast_config.yaml 讀取設定...")
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                
                level = config_data['basic']['english_level']
                article = config_data['input']['source']
                minutes = config_data['basic']['target_minutes']
                output_dir = config_data['advanced']['output_dir']
                host_voice = config_data['voices']['host_voice']
                expert_voice = config_data['voices']['expert_voice']
            else:
                print("🎯 使用預設設定生成播客...")
                level = "B2"
                article = "./sample_article.txt"
                minutes = 2
                output_dir = "./podcast_output"
                host_voice = "Kore"
                expert_voice = "Puck"
        
        print(f"\n" + "=" * 50)
        print(f"🎯 生成設定確認:")
        print(f"  📊 等級: {level}")
        print(f"  📄 文章: {article}")
        print(f"  ⏱️ 長度: {minutes} 分鐘")
        print(f"  📁 輸出: {output_dir}")
        print(f"  🎙️ 主持人: {host_voice}")
        print(f"  👨‍🏫 專家: {expert_voice}")
        print("=" * 50)
        
        # 非互動模式直接生成
        if len(sys.argv) <= 1:
            print("📝 按 Enter 確認生成，或 Ctrl+C 取消...")
            try:
                input()
            except:
                print("❌ 取消生成")
                return False
        
        # 檢查文章是否存在（如果是本地檔案）
        if article.startswith('./') and not Path(article).exists():
            print(f"❌ 文章檔案不存在: {article}")
            return False
        
        # 創建配置並生成
        print(f"\n🚀 開始生成...")
        # 統一使用完整參數創建配置
        config_path = create_quick_config(level, article, minutes, output_dir, host_voice, expert_voice)
        
        # 載入配置並生成
        from integrated_podcast_generator import IntegratedPodcastGenerator
        generator, config = IntegratedPodcastGenerator.from_config_file(config_path)
        result = generator.generate(config)
        
        # 清理臨時配置
        if Path(config_path).exists():
            Path(config_path).unlink()
        
        if result["status"] == "success":
            print(f"\n✅ 播客生成成功！")
            print(f"📁 輸出目錄: {result['output_dir']}")
            if "audio_file" in result:
                print(f"🎵 音頻檔案: {Path(result['audio_file']).name}")
            if "script_file" in result:
                print(f"📝 腳本檔案: {Path(result['script_file']).name}")
            
            # 顯示音頻檔案路徑
            if "audio_file" in result:
                print(f"\n🔗 音頻檔案路徑:")
                print(f"   {result['audio_file']}")
            
            # 顯示性能指標文件位置
            if "performance_metrics_file" in result:
                print(f"\n📊 性能指標檔案:")
                print(f"   {result['performance_metrics_file']}")
            
            return True
        else:
            print(f"\n❌ 生成失敗: {result.get('error')}")
            return False
            
    except KeyboardInterrupt:
        print(f"\n❌ 用戶取消操作")
        return False
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)