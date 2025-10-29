#!/usr/bin/env python3
"""Play an audio file while printing synchronized SRT subtitles to the terminal."""

from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class SubtitleLine:
    index: int
    start: float
    end: float
    text: str


def parse_srt(srt_path: Path) -> List[SubtitleLine]:
    """Parse an SRT file into structured subtitle lines."""
    raw = srt_path.read_text(encoding="utf-8").strip()
    blocks = raw.split("\n\n")

    def to_seconds(timestamp: str) -> float:
        hh, mm, rest = timestamp.split(":")
        ss, ms = rest.split(",")
        return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000

    subtitles: List[SubtitleLine] = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        index = int(lines[0])
        start_str, end_str = lines[1].split(" --> ")
        text = " ".join(lines[2:])
        subtitles.append(
            SubtitleLine(
                index=index,
                start=to_seconds(start_str),
                end=to_seconds(end_str),
                text=text,
            )
        )
    return subtitles


def detect_player(preferred: str | None = None) -> List[str]:
    """Return a playable command list for the first available audio player."""
    candidates = []
    if preferred:
        candidates.append(shlex.split(preferred))
    candidates.extend(
        [
            ["ffplay", "-nodisp", "-autoexit"],
            ["afplay"],
            ["mpv", "--no-video"],
        ]
    )

    for candidate in candidates:
        if shutil.which(candidate[0]):
            return candidate
    raise RuntimeError(
        "找不到可用的音頻播放器，請先安裝 ffplay/mpv 或指定 --player"
    )


def play_audio(audio_path: Path, player: List[str]) -> subprocess.Popen:
    """Spawn the audio player process."""
    cmd = player + [str(audio_path)]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_show(subtitles: List[SubtitleLine], limit: Optional[int] = None) -> bool:
    """Stream subtitles to stdout in sync with wall clock."""
    start_time = time.perf_counter()
    current_line = 0
    total = len(subtitles) if limit is None else min(limit, len(subtitles))

    try:
        while current_line < total:
            subtitle = subtitles[current_line]
            now = time.perf_counter() - start_time
            wait_time = subtitle.start - now
            if wait_time > 0:
                time.sleep(min(wait_time, 0.05))
                continue

            timestamp = format_timestamp(subtitle.start)
            duration = subtitle.end - subtitle.start
            print(f"\r[{timestamp} / +{duration:4.1f}s] {subtitle.text}      ")
            current_line += 1
    except KeyboardInterrupt:
        print("\n⏹️  手動停止字幕輸出。")
        return False
    return True


def format_timestamp(seconds: float) -> str:
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes):02d}:{secs:05.2f}"


def main():
    parser = argparse.ArgumentParser(
        description="Play audio while displaying synchronized subtitles"
    )
    parser.add_argument("audio", type=Path, help="音頻檔案 (wav/mp3/...)")
    parser.add_argument("srt", type=Path, help="對應的 SRT 字幕")
    parser.add_argument(
        "--player",
        type=str,
        help="指定播放器指令，例如 'afplay' 或 'ffplay -nodisp -autoexit'",
    )
    parser.add_argument(
        "--mute",
        action="store_true",
        help="僅顯示字幕，不播放音頻 (用於除錯)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="只顯示前 N 筆字幕，方便預覽",
    )

    args = parser.parse_args()

    if not args.audio.exists():
        parser.error(f"音頻檔案不存在: {args.audio}")
    if not args.srt.exists():
        parser.error(f"SRT 檔案不存在: {args.srt}")

    subtitles = parse_srt(args.srt)
    if not subtitles:
        parser.error("SRT 沒有可用字幕內容")

    audio_proc = None
    if not args.mute:
        player_cmd = detect_player(args.player)
        audio_proc = play_audio(args.audio, player_cmd)

    print("▶️  開始播放... 按 Ctrl+C 可提前停止")
    limit = None
    if args.limit is not None:
        if args.limit <= 0:
            parser.error("--limit 必須是正整數")
        limit = args.limit

    playback_finished = run_show(subtitles, limit=limit)

    if audio_proc:
        if not playback_finished and audio_proc.poll() is None:
            audio_proc.terminate()
        audio_proc.wait()


if __name__ == "__main__":
    main()
