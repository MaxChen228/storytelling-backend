#!/usr/bin/env python3
"""
模組化播客工作流程控制器
可以選擇：
1. 開發模式：步驟分離，每步確認
2. 生產模式：自動串接，一鍵完成
3. 自訂模式：選擇要執行的步驟
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
import argparse
import subprocess
from typing import Optional, Dict, Any

# 導入拆分版本的功能
from generate_script import generate_script_only
from generate_audio import generate_audio_from_script

class PodcastWorkflow:
    """播客生成工作流程控制器"""
    
    def __init__(self, mode: str = "dev", auto_confirm: bool = False):
        """
        Args:
            mode: 'dev'(開發模式), 'prod'(生產模式), 'custom'(自訂模式)
            auto_confirm: 是否自動確認每個步驟
        """
        self.mode = mode
        self.auto_confirm = auto_confirm
        self.script_dir = None
        self.audio_dir = None
        
    def confirm_step(self, message: str) -> bool:
        """確認是否繼續下一步"""
        if self.auto_confirm:
            return True
            
        print("\n" + "="*60)
        print(f"❓ {message}")
        print("="*60)
        
        while True:
            response = input("繼續執行？(y/n/view): ").lower().strip()
            if response == 'y':
                return True
            elif response == 'n':
                return False
            elif response == 'view' and self.script_dir:
                # 查看生成的腳本
                self.view_script()
            else:
                print("請輸入 y(繼續)、n(停止) 或 view(查看腳本)")
    
    def view_script(self):
        """查看生成的腳本內容"""
        if not self.script_dir:
            print("❌ 尚未生成腳本")
            return

        script_file = None
        script_path = Path(self.script_dir)
        if script_path.is_file() and script_path.suffix == ".json":
            try:
                session = json.loads(script_path.read_text(encoding='utf-8'))
                script_dirs = session.get("script_dirs") or []
                if script_dirs:
                    candidate = Path(script_dirs[0]) / "podcast_script.txt"
                    if candidate.exists():
                        script_file = candidate
            except json.JSONDecodeError:
                script_file = None
        else:
            candidate = script_path / "podcast_script.txt"
            if candidate.exists():
                script_file = candidate

        if not script_file or not script_file.exists():
            print("❌ 找不到可預覽的腳本")
            return

        print("\n" + "="*60)
        print("📝 腳本內容預覽（前50行）：")
        print("-"*60)
        with open(script_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for i, line in enumerate(lines[:50], 1):
                print(f"{i:3d} | {line.rstrip()}")
            if len(lines) > 50:
                print(f"... (還有 {len(lines)-50} 行)")
        print("="*60)
    
    def run_step1_script(self, config_path: str = "./podcast_config.yaml") -> Optional[str]:
        """執行步驟1：生成腳本"""
        print("\n🚀 步驟 1: 生成腳本")
        print("-"*60)
        
        try:
            # 調用 step1 的功能
            script_dir = generate_script_only(config_path)
            
            if script_dir:
                self.script_dir = script_dir
                
                # 顯示腳本統計
                session_path = Path(script_dir)
                session_info = None
                if session_path.is_file() and session_path.suffix == ".json":
                    try:
                        session_info = json.loads(session_path.read_text(encoding='utf-8'))
                    except json.JSONDecodeError:
                        session_info = None

                print(f"\n📊 腳本統計：")
                if session_info:
                    chapters = session_info.get('chapters', [])
                    print(f"   - 書籍: {session_info.get('book_name', 'N/A')}")
                    print(f"   - 章節數: {len(chapters)}")
                    for entry in chapters:
                        slug = entry.get('chapter_slug') or f"第 {entry.get('chapter_number')} 章"
                        print(f"     • {slug} → {entry.get('actual_words', 'N/A')} words")
                else:
                    metadata_file = session_path / "metadata.json"
                    if metadata_file.exists():
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        if metadata.get('entries'):
                            print(f"   - 章節數: {metadata.get('total_chapters')}")
                            print(f"   - 長度設定: {metadata.get('time_range', 'N/A')} / {metadata.get('target_words', 'N/A')} words")
                            for entry in metadata.get('entries', []):
                                print(f"     • 第 {entry['chapter_number']:02d} 章 → {entry['actual_words']} words")
                        else:
                            print(f"   - 播客長度: {metadata.get('podcast_length', 'N/A')} ({metadata.get('time_range', 'N/A')})")
                            print(f"   - 實際字數: {metadata.get('actual_words', 'N/A')}")
                            print(f"   - 目標字數: {metadata.get('target_words', 'N/A')}")
                            print(f"   - 準確度: {metadata.get('accuracy', 'N/A')}")
                
                return script_dir
            else:
                print("❌ 腳本生成失敗")
                return None
                
        except Exception as e:
            print(f"❌ 執行錯誤: {e}")
            return None
    
    def run_step2_audio(self, script_dir: str) -> Optional[str]:
        """執行步驟2：生成音頻"""
        print("\n🚀 步驟 2: 生成音頻")
        print("-"*60)
        
        try:
            # 調用 step2 的功能
            audio_dir = generate_audio_from_script(script_dir)
            
            if audio_dir:
                self.audio_dir = audio_dir
                audio_path = Path(audio_dir)
                if audio_path.is_file() and audio_path.suffix == ".json":
                    try:
                        audio_info = json.loads(audio_path.read_text(encoding='utf-8'))
                        chapters = audio_info.get('chapters', [])
                        print("\n📡 音頻統計：")
                        print(f"   - 書籍: {audio_info.get('book_name', 'N/A')}")
                        for entry in chapters:
                            print(f"     • {entry.get('chapter_slug', '章節')} → {entry.get('audio_dir')}")
                    except json.JSONDecodeError:
                        pass
                return audio_dir
            else:
                print("❌ 音頻生成失敗")
                return None
                
        except Exception as e:
            print(f"❌ 執行錯誤: {e}")
            return None
    
    def run_dev_mode(self, config_path: str = "./podcast_config.yaml"):
        """開發模式：兩步驟分離，可隨時中斷"""
        print("\n🔧 開發模式：兩步驟分離，可隨時中斷")
        
        # Step 1: 生成腳本
        script_dir = self.run_step1_script(config_path)
        if not script_dir:
            print("❌ 工作流程終止：腳本生成失敗")
            return False
        
        # 確認是否繼續生成音頻
        if not self.confirm_step("腳本已生成，是否繼續生成音頻？"):
            print("✅ 工作流程停止在腳本階段")
            print(f"📁 腳本位置: {script_dir}")
            return True
        
        # Step 2: 生成音頻
        audio_dir = self.run_step2_audio(script_dir)
        if not audio_dir:
            print("❌ 工作流程終止：音頻生成失敗")
            return False
        
        print("\n✅ 兩步驟工作流程完成！")
        print(f"📁 原始腳本: {script_dir}")
        print(f"📁 音頻位置: {audio_dir}")
        return True
    
    def run_prod_mode(self, config_path: str = "./podcast_config.yaml"):
        """生產模式：自動執行所有步驟"""
        print("\n⚡ 生產模式：自動執行兩步驟流程")
        
        # Step 1: 生成腳本
        script_dir = self.run_step1_script(config_path)
        if not script_dir:
            print("❌ 工作流程終止：腳本生成失敗")
            return False
        
        # Step 2: 生成音頻（自動繼續）
        audio_dir = self.run_step2_audio(script_dir)
        if not audio_dir:
            print("❌ 工作流程終止：音頻生成失敗")
            return False
        
        print("\n✅ 兩步驟工作流程完成！")
        print(f"📁 原始腳本: {script_dir}")
        print(f"📁 音頻位置: {audio_dir}")
        return True

    def run_custom_mode(self, config_path: str = "./podcast_config.yaml", 
                       steps: list = None, script_dir: str = None):
        """自訂模式：選擇要執行的步驟"""
        print("\n🎯 自訂模式：執行指定步驟")
        
        if not steps:
            steps = []
            print("請選擇要執行的步驟：")
            print("1. 生成腳本")
            print("2. 生成音頻（需要已有腳本）")
            print("3. 完整流程（腳本 → 音頻）")
            
            choice = input("選擇 (1-3): ").strip()
            if choice == '1':
                steps = ['script']
            elif choice == '2':
                steps = ['audio']
            elif choice == '3':
                steps = ['script', 'audio']
            else:
                print("❌ 無效選擇")
                return False
        
        # 執行選定的步驟
        if 'script' in steps:
            script_dir = self.run_step1_script(config_path)
            if not script_dir:
                print("❌ 腳本生成失敗")
                return False
        
        if 'audio' in steps:
            if not script_dir:
                # 需要指定腳本目錄
                print("請提供腳本目錄路徑：")
                script_dir = input("腳本路徑: ").strip()
                if not Path(script_dir).exists():
                    print("❌ 腳本目錄不存在")
                    return False
            
            audio_dir = self.run_step2_audio(script_dir)
            if not audio_dir:
                print("❌ 音頻生成失敗")
                return False
        
        print("\n✅ 自訂工作流程完成！")
        return True
    
    def run(self, config_path: str = "./podcast_config.yaml", **kwargs):
        """執行工作流程"""
        print("="*60)
        print("🎙️ 播客生成工作流程")
        print("="*60)
        
        if self.mode == "dev":
            return self.run_dev_mode(config_path)
        elif self.mode == "prod":
            return self.run_prod_mode(config_path)
        elif self.mode == "custom":
            return self.run_custom_mode(config_path, **kwargs)
        else:
            print(f"❌ 未知模式: {self.mode}")
            return False


def main():
    """主程式入口"""
    parser = argparse.ArgumentParser(description='模組化播客生成工作流程')
    parser.add_argument('--mode', choices=['dev', 'prod', 'custom'], 
                       default='dev', help='執行模式')
    parser.add_argument('--config', default='./podcast_config.yaml',
                       help='配置文件路徑')
    parser.add_argument('--auto-confirm', action='store_true',
                       help='自動確認所有步驟（開發模式）')
    parser.add_argument('--steps', nargs='+', 
                       choices=['script', 'audio'],
                       help='自訂模式要執行的步驟')
    parser.add_argument('--script-dir', help='已有腳本的目錄（用於單獨生成音頻）')
    
    args = parser.parse_args()
    
    # 創建工作流程控制器
    workflow = PodcastWorkflow(mode=args.mode, auto_confirm=args.auto_confirm)
    
    # 執行工作流程
    success = workflow.run(
        config_path=args.config,
        steps=args.steps,
        script_dir=args.script_dir
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
