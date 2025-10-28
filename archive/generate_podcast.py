#!/usr/bin/env python3
"""
簡易播客生成器
只需調整 podcast_config.yaml 即可自定義所有參數
"""

import sys
from pathlib import Path
from integrated_podcast_generator import generate_from_config


def main():
    """主程序：從配置文件生成播客"""
    print("🎯 播客生成器")
    print("=" * 50)
    
    # 檢查配置文件
    config_file = Path("./podcast_config.yaml")
    if not config_file.exists():
        print("❌ 找不到配置文件: podcast_config.yaml")
        print("請先創建配置文件或使用預設配置")
        return False
    
    print("📄 使用配置文件: podcast_config.yaml")
    print("💡 修改配置文件即可調整所有參數")
    print("-" * 50)
    
    # 生成播客
    result = generate_from_config()
    
    if result["status"] == "success":
        print(f"\n✅ 播客生成成功！")
        print(f"📁 輸出目錄: {result['output_dir']}")
        if "audio_file" in result:
            print(f"🎵 音頻檔案: {Path(result['audio_file']).name}")
        if "script_file" in result:
            print(f"📝 腳本檔案: {Path(result['script_file']).name}")
        return True
    else:
        print(f"\n❌ 生成失敗: {result.get('error')}")
        return False


if __name__ == "__main__":
    main()