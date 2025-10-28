#!/usr/bin/env python3
"""
舊資料遷移腳本：將時間戳記版本遷移到書本/章節結構

舊架構:
  output/scripts/storytelling_batch_20251026_211021/chapter0/
  output/audio/storytelling/audio_20251026_211651/chapter0/

新架構:
  output/foundation/chapter0/
    ├── podcast_script.txt
    ├── podcast.wav (如果有)
    └── metadata.json
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime

class FoundationMigrator:
    """Foundation 專案資料遷移工具"""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.old_scripts_dir = self.base_dir / "output" / "scripts"
        self.old_audio_dir = self.base_dir / "output" / "audio"
        self.new_foundation_dir = self.base_dir / "output" / "foundation"

    def scan_old_data(self):
        """掃描舊資料結構"""
        print("=" * 70)
        print("📊 掃描舊資料結構")
        print("=" * 70)

        # 掃描腳本
        script_batches = []
        if self.old_scripts_dir.exists():
            for batch_dir in self.old_scripts_dir.iterdir():
                if batch_dir.is_dir() and batch_dir.name.startswith('storytelling_batch_'):
                    manifest_file = batch_dir / "batch_manifest.json"
                    if manifest_file.exists():
                        with open(manifest_file, 'r', encoding='utf-8') as f:
                            manifest = json.load(f)
                        script_batches.append({
                            'path': batch_dir,
                            'manifest': manifest,
                            'timestamp': manifest.get('batch_timestamp')
                        })

        # 掃描音頻
        audio_batches = []
        if self.old_audio_dir.exists():
            storytelling_dir = self.old_audio_dir / "storytelling"
            if storytelling_dir.exists():
                for audio_dir in storytelling_dir.iterdir():
                    if audio_dir.is_dir() and audio_dir.name.startswith('audio_'):
                        manifest_file = audio_dir / "batch_manifest.json"
                        if manifest_file.exists():
                            with open(manifest_file, 'r', encoding='utf-8') as f:
                                manifest = json.load(f)
                            audio_batches.append({
                                'path': audio_dir,
                                'manifest': manifest,
                                'timestamp': manifest.get('timestamp')
                            })

        print(f"✓ 找到 {len(script_batches)} 個腳本批次")
        for batch in script_batches:
            print(f"  - {batch['path'].name} ({batch['manifest'].get('total_chapters', 0)} 章節)")

        print(f"\n✓ 找到 {len(audio_batches)} 個音頻批次")
        for batch in audio_batches:
            print(f"  - {batch['path'].name} ({len(batch['manifest'].get('chapters', []))} 章節)")

        return script_batches, audio_batches

    def build_chapter_map(self, script_batches, audio_batches):
        """建立章節對應關係"""
        print("\n" + "=" * 70)
        print("🗺️ 建立章節對應關係")
        print("=" * 70)

        chapter_map = {}

        # 處理腳本
        for batch in script_batches:
            for entry in batch['manifest'].get('entries', []):
                chapter_title = entry.get('title')
                chapter_num = entry.get('chapter_number')

                if chapter_title not in chapter_map:
                    chapter_map[chapter_title] = {
                        'chapter_number': chapter_num,
                        'scripts': [],
                        'audios': [],
                        'metadata': {}
                    }

                chapter_map[chapter_title]['scripts'].append({
                    'path': batch['path'] / entry.get('output_folder_name'),
                    'timestamp': batch['timestamp'],
                    'metadata': entry
                })

        # 處理音頻
        for batch in audio_batches:
            for chapter_path in batch['manifest'].get('chapters', []):
                # 提取章節名稱
                chapter_name = Path(chapter_path).name

                if chapter_name in chapter_map:
                    chapter_map[chapter_name]['audios'].append({
                        'path': batch['path'] / chapter_name,
                        'timestamp': batch['timestamp']
                    })

        # 顯示對應關係
        for chapter, data in sorted(chapter_map.items()):
            print(f"\n📖 {chapter} (章節 {data['chapter_number']})")
            print(f"   腳本: {len(data['scripts'])} 個版本")
            for script in data['scripts']:
                print(f"      - {script['timestamp']}: {script['path']}")
            print(f"   音頻: {len(data['audios'])} 個版本")
            for audio in data['audios']:
                print(f"      - {audio['timestamp']}: {audio['path']}")

        return chapter_map

    def migrate_chapter(self, chapter_name, chapter_data, dry_run=False):
        """遷移單個章節"""
        target_dir = self.new_foundation_dir / chapter_name

        print(f"\n📦 遷移 {chapter_name}")
        print(f"   目標: {target_dir}")

        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)

        # 選擇最新的腳本版本
        if chapter_data['scripts']:
            latest_script = max(chapter_data['scripts'],
                              key=lambda x: x['timestamp'])

            script_file = latest_script['path'] / "podcast_script.txt"
            metadata_file = latest_script['path'] / "metadata.json"

            if script_file.exists():
                print(f"   ✓ 複製腳本 (版本: {latest_script['timestamp']})")
                if not dry_run:
                    shutil.copy2(script_file, target_dir / "podcast_script.txt")

            if metadata_file.exists():
                # 讀取並更新元數據
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)

                # 添加遷移資訊
                metadata['migration'] = {
                    'migrated_at': datetime.now().isoformat(),
                    'old_path': str(latest_script['path']),
                    'script_versions': [
                        {
                            'timestamp': s['timestamp'],
                            'path': str(s['path'])
                        } for s in chapter_data['scripts']
                    ]
                }

                print(f"   ✓ 更新元數據")
                if not dry_run:
                    with open(target_dir / "metadata.json", 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)

        # 選擇最新的音頻版本
        if chapter_data['audios']:
            latest_audio = max(chapter_data['audios'],
                             key=lambda x: x['timestamp'])

            audio_file = latest_audio['path'] / "podcast.wav"
            audio_metadata = latest_audio['path'] / "metadata.json"

            if audio_file.exists():
                print(f"   ✓ 複製音頻 (版本: {latest_audio['timestamp']})")
                if not dry_run:
                    shutil.copy2(audio_file, target_dir / "podcast.wav")

            if audio_metadata.exists():
                # 合併音頻元數據
                with open(audio_metadata, 'r', encoding='utf-8') as f:
                    audio_meta = json.load(f)

                metadata_path = target_dir / "metadata.json"
                if metadata_path.exists() and not dry_run:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        full_metadata = json.load(f)

                    full_metadata['audio'] = audio_meta
                    full_metadata['migration']['audio_versions'] = [
                        {
                            'timestamp': a['timestamp'],
                            'path': str(a['path'])
                        } for a in chapter_data['audios']
                    ]

                    with open(metadata_path, 'w', encoding='utf-8') as f:
                        json.dump(full_metadata, f, indent=2, ensure_ascii=False)

        return True

    def run(self, dry_run=True):
        """執行遷移"""
        print("=" * 70)
        print(f"🚀 Foundation 資料遷移工具")
        print(f"   模式: {'模擬運行 (不實際複製)' if dry_run else '實際執行'}")
        print("=" * 70)

        # 1. 掃描舊資料
        script_batches, audio_batches = self.scan_old_data()

        if not script_batches and not audio_batches:
            print("\n⚠️  未找到任何舊資料")
            return False

        # 2. 建立章節對應關係
        chapter_map = self.build_chapter_map(script_batches, audio_batches)

        if not chapter_map:
            print("\n⚠️  無法建立章節對應關係")
            return False

        # 3. 執行遷移
        print("\n" + "=" * 70)
        print("🔄 開始遷移")
        print("=" * 70)

        success_count = 0
        for chapter_name, chapter_data in sorted(chapter_map.items()):
            try:
                if self.migrate_chapter(chapter_name, chapter_data, dry_run):
                    success_count += 1
            except Exception as e:
                print(f"   ✗ 錯誤: {e}")

        # 4. 摘要
        print("\n" + "=" * 70)
        print("📊 遷移摘要")
        print("=" * 70)
        print(f"成功遷移: {success_count}/{len(chapter_map)} 個章節")

        if dry_run:
            print("\n💡 這是模擬運行，沒有實際複製檔案")
            print("   若要實際執行遷移，請使用: --execute 參數")
        else:
            print(f"\n✅ 資料已遷移到: {self.new_foundation_dir}")
            print("\n📝 建議後續步驟:")
            print("   1. 驗證新目錄的內容")
            print("   2. 確認無誤後，可以刪除舊的 scripts 和 audio 目錄")
            print("   3. 或將舊目錄重命名為 scripts_backup 和 audio_backup")

        return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Foundation 資料遷移工具')
    parser.add_argument('--base-dir',
                       default='/Users/chenliangyu/Desktop/story telling podcast',
                       help='專案根目錄')
    parser.add_argument('--execute', action='store_true',
                       help='實際執行遷移（預設為模擬運行）')

    args = parser.parse_args()

    migrator = FoundationMigrator(args.base_dir)
    migrator.run(dry_run=not args.execute)


if __name__ == "__main__":
    main()
