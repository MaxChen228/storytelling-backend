#!/usr/bin/env python3
"""Generate word-level subtitles (SRT + JSON) for a podcast chapter.

This wraps the WhisperX alignment utility located under
`whisperx_alignment_test/scripts/align_audio.py`, handling
path resolution for the Foundation workflow and providing
a simple CLI interface used by `run.sh`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

# 動態加入測試工具路徑
SCRIPT_ROOT = Path(__file__).resolve().parent
ALIGNMENT_DIR = SCRIPT_ROOT / "whisperx_alignment_test" / "scripts"
if ALIGNMENT_DIR.exists():
    sys.path.insert(0, str(ALIGNMENT_DIR))

try:
    from align_audio import (
        align_with_whisperx,
        generate_srt,
        resolve_device,
        save_alignment_json,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - 確保有明確錯誤訊息
    raise SystemExit(
        "找不到 whisperx alignment 工具，請確認專案目錄結構: "
        "whisperx_alignment_test/scripts/align_audio.py"
    ) from exc

from text_cleaner import clean_script_for_alignment, prepare_segments

DEFAULT_FOUNDATION_DIR = SCRIPT_ROOT / "output" / "foundation"


def detect_audio_file(chapter_dir: Path) -> Optional[Path]:
    """優先尋找 wav，其次 mp3。"""
    for name in ("podcast.wav", "podcast.mp3"):
        candidate = chapter_dir / name
        if candidate.exists():
            return candidate
    return None


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate subtitles via WhisperX")
    parser.add_argument(
        "chapter",
        help="章節名稱 (例如 chapter3) 或章節輸出的絕對路徑",
    )
    parser.add_argument(
        "--device",
        default="auto",
        help="裝置：auto/cpu/mps/cuda (預設 auto)",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="語言代碼，預設 en",
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=32,
        help="腳本對齊時每段最大詞數 (預設 32，較容易維持語速)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="已存在字幕時覆寫",
    )
    parser.add_argument(
        "--vad",
        default="silero",
        choices=["silero", "pyannote"],
        help="語音活動偵測 (VAD) 模型，預設 silero 以避免舊版 pyannote 依賴",
    )
    parser.add_argument(
        "--model",
        default="small",
        choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"],
        help="Whisper 模型尺寸，預設 small",
    )

    args = parser.parse_args(argv)

    # 解析章節路徑
    chapter_input = Path(args.chapter)
    if chapter_input.is_dir():
        chapter_dir = chapter_input
    else:
        chapter_dir = DEFAULT_FOUNDATION_DIR / chapter_input.name

    script_path = chapter_dir / "podcast_script.txt"
    audio_path = detect_audio_file(chapter_dir)
    json_output = chapter_dir / "aligned_transcript.json"
    srt_output = chapter_dir / "subtitles.srt"

    if not script_path.exists():
        print(f"❌ 找不到腳本檔案：{script_path}")
        return 1
    if audio_path is None:
        print(f"❌ 找不到音頻檔案：{chapter_dir}/podcast.(wav|mp3)")
        return 1

    if (json_output.exists() or srt_output.exists()) and not args.force:
        print("⚠️  字幕檔已存在，如需覆寫請加上 --force")
        print(f"  JSON: {json_output}")
        print(f"  SRT : {srt_output}")
        return 0

    print("=" * 60)
    print("🎯 生成字幕")
    print("=" * 60)
    print(f"📖 章節: {chapter_dir.name}")
    print(f"📂 音頻: {audio_path}")
    print(f"📝 腳本: {script_path}")

    raw_text = script_path.read_text(encoding="utf-8")
    cleaned = clean_script_for_alignment(raw_text)
    segments = prepare_segments(raw_text, max_words_per_segment=args.max_words)

    device = resolve_device(args.device)
    try:
        result = align_with_whisperx(
            audio_path=audio_path,
            device=device,
            language=args.language,
            reference_text=cleaned,
            segments_override=segments,
            vad_method=args.vad,
            whisper_model=args.model,
        )
    except Exception as exc:  # pragma: no cover - 顯示友善訊息
        print(f"\n❌ WhisperX 對齊失敗：{exc}")
        return 1

    save_alignment_json(result, json_output)
    generate_srt(result, srt_output)

    print("\n✅ 字幕已產生")
    print(f"  JSON: {json_output}")
    print(f"  SRT : {srt_output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
