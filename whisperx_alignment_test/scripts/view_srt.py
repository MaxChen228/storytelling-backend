#!/usr/bin/env python3
"""
SRT 字幕查看工具
將 SRT 轉換成更易讀的格式
"""

import re
from pathlib import Path
from typing import List, Tuple


def parse_srt(srt_path: Path) -> List[Tuple[int, str, str, str]]:
    """解析 SRT 文件"""
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 分割每個字幕區塊
    blocks = content.strip().split('\n\n')

    subtitles = []
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            index = int(lines[0])
            timestamp = lines[1]
            text = ' '.join(lines[2:])

            # 解析時間
            times = timestamp.split(' --> ')
            start_time = times[0]
            end_time = times[1]

            subtitles.append((index, start_time, end_time, text))

    return subtitles


def format_time(time_str: str) -> str:
    """簡化時間顯示"""
    # 00:00:16,126 -> 16.126s
    parts = time_str.split(':')
    seconds = parts[2].replace(',', '.')
    minutes = int(parts[1])

    if minutes > 0:
        return f"{minutes}:{seconds}s"
    else:
        return f"{seconds}s"


def view_srt_timeline(srt_path: Path, words_per_line: int = 10):
    """以時間軸方式顯示字幕"""
    subtitles = parse_srt(srt_path)

    print("=" * 80)
    print(f"📺 SRT 字幕查看器")
    print(f"📄 文件: {srt_path.name}")
    print(f"📊 總詞數: {len(subtitles)}")
    print("=" * 80)
    print()

    # 按行顯示
    for i in range(0, len(subtitles), words_per_line):
        chunk = subtitles[i:i+words_per_line]

        # 顯示時間範圍
        start_time = format_time(chunk[0][1])
        end_time = format_time(chunk[-1][2])
        print(f"\n⏱️  [{start_time} → {end_time}]")

        # 顯示詞彙
        words = [sub[3] for sub in chunk]
        print("   " + ' '.join(words))


def view_srt_detailed(srt_path: Path, start_index: int = 1, count: int = 20):
    """詳細顯示字幕（含精確時間戳）"""
    subtitles = parse_srt(srt_path)

    print("=" * 80)
    print(f"📺 SRT 詳細檢視")
    print(f"📄 文件: {srt_path.name}")
    print("=" * 80)
    print()

    end_index = min(start_index + count, len(subtitles) + 1)

    for sub in subtitles[start_index-1:end_index-1]:
        index, start, end, text = sub
        print(f"{index:4d}  {format_time(start):>8s} → {format_time(end):>8s}  │ {text}")


def search_word(srt_path: Path, keyword: str):
    """搜尋特定詞彙"""
    subtitles = parse_srt(srt_path)

    print("=" * 80)
    print(f"🔍 搜尋關鍵字: '{keyword}'")
    print("=" * 80)
    print()

    matches = []
    for sub in subtitles:
        index, start, end, text = sub
        if keyword.lower() in text.lower():
            matches.append(sub)

    if not matches:
        print(f"❌ 找不到 '{keyword}'")
        return

    print(f"✅ 找到 {len(matches)} 個結果：\n")

    for sub in matches:
        index, start, end, text = sub
        print(f"{index:4d}  {format_time(start):>8s}  │ {text}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="SRT 字幕查看工具")
    parser.add_argument('srt_file', help='SRT 文件路徑')
    parser.add_argument('--mode', choices=['timeline', 'detailed', 'search'],
                       default='timeline', help='查看模式')
    parser.add_argument('--words-per-line', type=int, default=10,
                       help='時間軸模式：每行顯示詞數')
    parser.add_argument('--start', type=int, default=1,
                       help='詳細模式：起始序號')
    parser.add_argument('--count', type=int, default=20,
                       help='詳細模式：顯示數量')
    parser.add_argument('--keyword', type=str,
                       help='搜尋模式：關鍵字')

    args = parser.parse_args()
    srt_path = Path(args.srt_file)

    if not srt_path.exists():
        print(f"❌ 文件不存在: {srt_path}")
        return

    if args.mode == 'timeline':
        view_srt_timeline(srt_path, args.words_per_line)
    elif args.mode == 'detailed':
        view_srt_detailed(srt_path, args.start, args.count)
    elif args.mode == 'search':
        if not args.keyword:
            print("❌ 搜尋模式需要提供 --keyword 參數")
            return
        search_word(srt_path, args.keyword)


if __name__ == "__main__":
    main()
