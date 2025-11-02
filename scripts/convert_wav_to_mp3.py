#!/usr/bin/env python3
"""Backfill MP3 files alongside existing podcast.wav outputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydub import AudioSegment


def convert_chapter(chapter_dir: Path, bitrate: str) -> str:
    wav_path = chapter_dir / "podcast.wav"
    mp3_path = chapter_dir / "podcast.mp3"

    if not wav_path.exists():
        return "missing"

    if mp3_path.exists() and mp3_path.stat().st_mtime >= wav_path.stat().st_mtime:
        return "up_to_date"

    try:
        audio = AudioSegment.from_file(wav_path)
        audio.export(str(mp3_path), format="mp3", bitrate=bitrate)
        return "converted"
    except Exception as exc:
        print(f"⚠️  無法轉換 {wav_path}：{exc}")
        return "error"


def iter_chapter_dirs(root: Path) -> list[Path]:
    result: list[Path] = []
    for book_dir in root.iterdir():
        if not book_dir.is_dir():
            continue
        for chapter_dir in sorted(book_dir.glob("chapter*")):
            if chapter_dir.is_dir():
                result.append(chapter_dir)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert podcast.wav files to podcast.mp3 for all chapters.")
    parser.add_argument("--output-root", default="output", help="根目錄（預設：output）")
    parser.add_argument("--bitrate", default="192k", help="輸出 MP3 比特率（預設 192k）")
    args = parser.parse_args()

    root = Path(args.output_root).expanduser().resolve()
    if not root.exists():
        print(f"❌ 找不到 output 根目錄：{root}")
        return 1

    converted = 0
    skipped = 0
    missing = 0
    errors = 0

    for chapter_dir in iter_chapter_dirs(root):
        status = convert_chapter(chapter_dir, args.bitrate)
        if status == "converted":
            converted += 1
            print(f"🎧 生成 MP3：{chapter_dir / 'podcast.mp3'}")
        elif status == "up_to_date":
            skipped += 1
        elif status == "missing":
            missing += 1
        else:
            errors += 1

    print()
    print(f"完成！轉換 {converted} 個章節，跳過 {skipped} 個（已是最新），缺少 WAV {missing} 個，失敗 {errors} 個。")
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
