"""Chapter scanning utilities for the storytelling CLI."""

from __future__ import annotations

import re
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class ChapterStatus:
    """Represents the generation state of a single chapter."""

    slug: str
    has_source: bool
    has_summary: bool
    has_script: bool
    has_audio: bool
    has_subtitle: bool
    audio_duration: Optional[float] = None
    audio_subtitle_gap: Optional[float] = None


def natural_key(text: str) -> Tuple[object, ...]:
    """Human-friendly sort key that keeps embedded numbers in order."""
    parts = re.split(r"(\d+)", text)
    key: List[object] = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part.lower())
    return tuple(key)


def scan_chapters(
    book_dir: Path,
    summary_dir: Path,
    summary_suffix: str,
    output_dir: Path,
) -> List[ChapterStatus]:
    """Inspect chapter folders/files and build their status summary."""
    chapters_set = set()

    if book_dir.exists():
        for file in book_dir.glob("*.txt"):
            chapters_set.add(file.stem)

    if output_dir.exists():
        for directory in output_dir.glob("chapter*"):
            if directory.is_dir():
                chapters_set.add(directory.name)

    sorted_slugs = sorted(chapters_set, key=natural_key)
    statuses: List[ChapterStatus] = []

    for slug in sorted_slugs:
        source = (book_dir / f"{slug}.txt").exists()
        summary = (summary_dir / f"{slug}{summary_suffix}").exists()

        chapter_dir = output_dir / slug
        script = (chapter_dir / "podcast_script.txt").exists()
        audio = (chapter_dir / "podcast.wav").exists() or (chapter_dir / "podcast.mp3").exists()
        subtitle = (chapter_dir / "subtitles.srt").exists()

        audio_duration = _chapter_audio_duration(chapter_dir) if audio else None
        subtitle_end = _chapter_last_subtitle_end(chapter_dir) if subtitle else None

        gap: Optional[float] = None
        if audio_duration is not None and subtitle_end is not None:
            gap = audio_duration - subtitle_end

        statuses.append(
            ChapterStatus(
                slug=slug,
                has_source=source,
                has_summary=summary,
                has_script=script,
                has_audio=audio,
                has_subtitle=subtitle,
                audio_duration=audio_duration,
                audio_subtitle_gap=gap,
            )
        )

    return statuses


def _chapter_audio_duration(chapter_dir: Path) -> Optional[float]:
    wav_path = chapter_dir / "podcast.wav"
    if wav_path.exists():
        try:
            with wave.open(str(wav_path), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate() or 1
            return frames / max(rate, 1)
        except (OSError, wave.Error):
            return None

    mp3_path = chapter_dir / "podcast.mp3"
    if mp3_path.exists():
        try:
            from pydub import AudioSegment  # lazy import

            audio = AudioSegment.from_file(mp3_path)
            return len(audio) / 1000.0
        except Exception:
            return None

    return None


def _parse_srt_timestamp(raw: str) -> Optional[float]:
    raw = raw.strip()
    if not raw:
        return None
    try:
        hours, minutes, remainder = raw.split(":")
    except ValueError:
        return None
    try:
        seconds, millis = remainder.split(",")
    except ValueError:
        return None

    try:
        return (
            int(hours) * 3600
            + int(minutes) * 60
            + int(seconds)
            + int(millis) / 1000.0
        )
    except ValueError:
        return None


def _chapter_last_subtitle_end(chapter_dir: Path) -> Optional[float]:
    srt_path = chapter_dir / "subtitles.srt"
    if not srt_path.exists():
        return None
    try:
        content = srt_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = srt_path.read_text(encoding="utf-8", errors="ignore")

    for line in reversed(content.splitlines()):
        if "-->" not in line:
            continue
        try:
            _, end = line.split("-->")
        except ValueError:
            continue
        ts = _parse_srt_timestamp(end)
        if ts is not None:
            return ts
    return None

