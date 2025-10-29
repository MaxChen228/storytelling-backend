"""輕量化的檔案系統快取，僅提供前端需要的欄位。"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from threading import RLock
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SubtitleData:
    srt_path: Optional[Path] = None


@dataclass
class ChapterData:
    id: str
    title: str
    number: Optional[int]
    path: Path
    metadata: Dict[str, object]
    audio_file: Optional[Path]
    audio_mime_type: Optional[str]
    subtitles: Optional[SubtitleData]
    word_count: Optional[int]
    audio_duration_sec: Optional[float]
    words_per_minute: Optional[float]


@dataclass
class SubtitleMetrics:
    word_count: Optional[int]
    audio_duration_sec: Optional[float]
    words_per_minute: Optional[float]


@dataclass
class BookData:
    id: str
    root: Path
    metadata: Dict[str, object]
    chapters: Dict[str, ChapterData]


class OutputDataCache:
    """Caches parsed data from the output directory to serve API requests efficiently."""

    def __init__(self, data_root: Path):
        self.data_root = Path(data_root)
        self._lock = RLock()
        self._books: Dict[str, BookData] = {}
        self._signature: Optional[str] = None

    def refresh(self, force: bool = False) -> None:
        """Refreshes the cache if the underlying data changed or when forced."""
        with self._lock:
            signature = self._compute_signature()
            if not force and signature == self._signature:
                return
            logger.info("Refreshing output cache for %s", self.data_root)
            self._books = self._scan_books()
            self._signature = signature

    def clear(self) -> None:
        with self._lock:
            self._books = {}
            self._signature = None

    def get_books(self) -> Dict[str, BookData]:
        self.refresh()
        return self._books

    def get_book(self, book_id: str) -> Optional[BookData]:
        self.refresh()
        return self._books.get(book_id)

    def get_chapter(self, book_id: str, chapter_id: str) -> Optional[ChapterData]:
        book = self.get_book(book_id)
        if not book:
            return None
        return book.chapters.get(chapter_id)

    # Internal helpers -----------------------------------------------------

    def _compute_signature(self) -> str:
        """Computes a cheap hash over file metadata to detect changes."""
        hasher = sha256()
        if not self.data_root.exists():
            return hasher.hexdigest()

        relevant_suffixes = {".json", ".srt", ".wav", ".mp3", ".m4a"}
        for path in sorted(self.data_root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in relevant_suffixes:
                continue
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            rel = str(path.relative_to(self.data_root)).encode("utf-8", errors="ignore")
            hasher.update(rel)
            hasher.update(str(stat.st_mtime_ns).encode("ascii"))
            hasher.update(str(stat.st_size).encode("ascii"))
        return hasher.hexdigest()

    def _scan_books(self) -> Dict[str, BookData]:
        books: Dict[str, BookData] = {}
        if not self.data_root.exists():
            logger.warning("Data root %s does not exist", self.data_root)
            return books

        for book_dir in sorted(p for p in self.data_root.iterdir() if p.is_dir()):
            book_id = book_dir.name
            book_data = self._load_book(book_id, book_dir)
            if book_data:
                books[book_id] = book_data
        return books

    def _load_book(self, book_id: str, book_dir: Path) -> Optional[BookData]:
        metadata_obj = self._read_json(book_dir / "book_metadata.json")
        if not isinstance(metadata_obj, dict):
            metadata_obj = {}

        chapters = self._load_chapters(book_dir)

        return BookData(
            id=book_id,
            root=book_dir,
            metadata=metadata_obj,
            chapters=chapters,
        )

    def _load_chapters(self, book_dir: Path) -> Dict[str, ChapterData]:
        chapters: Dict[str, ChapterData] = {}

        for chapter_dir in sorted(p for p in book_dir.iterdir() if p.is_dir() and p.name.startswith("chapter")):
            chapter_id = chapter_dir.name
            chapter = self._load_chapter(chapter_id, chapter_dir)
            if chapter:
                chapters[chapter_id] = chapter

        return chapters

    def _load_chapter(self, chapter_id: str, chapter_dir: Path) -> Optional[ChapterData]:
        metadata_path = chapter_dir / "metadata.json"
        metadata_obj = self._read_json(metadata_path) or {}
        if not isinstance(metadata_obj, dict):
            metadata_obj = {}

        chapter_number = metadata_obj.get("chapter_number")
        if isinstance(chapter_number, str) and chapter_number.isdigit():
            chapter_number = int(chapter_number)
        elif not isinstance(chapter_number, int):
            chapter_number = None

        chapter_title = str(metadata_obj.get("chapter_title") or chapter_id)

        audio_file, audio_mime = self._locate_audio_file(chapter_dir)
        subtitles = self._load_subtitles(chapter_dir)

        word_count = self._coerce_int(metadata_obj.get("actual_words") or metadata_obj.get("word_count"))
        audio_duration_sec = self._coerce_float(metadata_obj.get("audio_duration_sec") or metadata_obj.get("duration_seconds"))
        words_per_minute = self._coerce_float(metadata_obj.get("words_per_minute") or metadata_obj.get("wpm"))

        if subtitles and subtitles.srt_path:
            metrics = self._calculate_subtitle_metrics(subtitles.srt_path)
            if metrics:
                if word_count is None and metrics.word_count is not None:
                    word_count = metrics.word_count
                if audio_duration_sec is None and metrics.audio_duration_sec is not None:
                    audio_duration_sec = metrics.audio_duration_sec
                if words_per_minute is None and metrics.words_per_minute is not None:
                    words_per_minute = metrics.words_per_minute

                # 將推算結果補充回 metadata 供 API 使用
                if metrics.word_count is not None:
                    metadata_obj.setdefault("word_count", metrics.word_count)
                if metrics.audio_duration_sec is not None:
                    metadata_obj.setdefault("audio_duration_sec", metrics.audio_duration_sec)
                if metrics.words_per_minute is not None:
                    metadata_obj.setdefault("words_per_minute", metrics.words_per_minute)

        return ChapterData(
            id=chapter_id,
            title=chapter_title,
            number=chapter_number,
            path=chapter_dir,
            metadata=metadata_obj,
            audio_file=audio_file,
            audio_mime_type=audio_mime,
            subtitles=subtitles,
            word_count=word_count,
            audio_duration_sec=audio_duration_sec,
            words_per_minute=words_per_minute,
        )

    def _locate_audio_file(self, chapter_dir: Path) -> tuple[Optional[Path], Optional[str]]:
        audio_candidates = [
            ("podcast.wav", "audio/wav"),
            ("podcast.mp3", "audio/mpeg"),
            ("podcast.m4a", "audio/mp4"),
        ]
        for filename, mime_type in audio_candidates:
            path = chapter_dir / filename
            if path.exists():
                return path, mime_type
        return None, None

    def _load_subtitles(self, chapter_dir: Path) -> Optional[SubtitleData]:
        srt_path = chapter_dir / "subtitles.srt"
        if not srt_path.exists():
            return None
        return SubtitleData(srt_path=srt_path)

    def _calculate_subtitle_metrics(self, srt_path: Path) -> Optional[SubtitleMetrics]:
        try:
            content = srt_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to read subtitles %s: %s", srt_path, exc)
            return None

        blocks = re.split(r"\n\s*\n", content.strip())
        if not blocks:
            return None

        time_pattern = re.compile(r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2},\d{3})")
        word_pattern = re.compile(r"[A-Za-z][A-Za-z'\-]*")

        start_times: List[float] = []
        end_times: List[float] = []
        total_words = 0

        for raw_block in blocks:
            lines = [line.strip() for line in raw_block.splitlines() if line.strip()]
            if len(lines) < 2:
                continue

            time_line: Optional[str] = None
            for line in lines[1:]:
                if "-->" in line:
                    time_line = line
                    break
            if not time_line:
                continue

            match = time_pattern.search(time_line)
            if not match:
                continue

            start = self._parse_srt_timestamp(match.group("start"))
            end = self._parse_srt_timestamp(match.group("end"))
            if start is None or end is None or end <= start:
                continue

            start_times.append(start)
            end_times.append(end)

            time_index = lines.index(time_line)
            text_lines = lines[time_index + 1 :]
            if not text_lines:
                continue

            text_without_tags = re.sub(r"<[^>]+>", " ", " ".join(text_lines))
            words = word_pattern.findall(text_without_tags)
            total_words += len(words)

        if not start_times:
            return None

        duration = max(end_times) - min(start_times)
        duration_sec: Optional[float]
        if duration <= 0:
            duration_sec = None
        else:
            duration_sec = round(duration, 3)

        word_count = total_words if total_words > 0 else None

        words_per_minute: Optional[float] = None
        if word_count is not None and duration_sec and duration_sec > 0:
            words_per_minute = round(word_count / (duration_sec / 60.0), 1)

        return SubtitleMetrics(
            word_count=word_count,
            audio_duration_sec=duration_sec,
            words_per_minute=words_per_minute,
        )

    @staticmethod
    def _parse_srt_timestamp(raw: str) -> Optional[float]:
        match = re.match(r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})$", raw.strip())
        if not match:
            return None
        hours, minutes, seconds, millis = match.groups()
        try:
            total_seconds = (
                int(hours) * 3600
                + int(minutes) * 60
                + int(seconds)
                + int(millis) / 1000.0
            )
        except ValueError:
            return None
        return float(total_seconds)

    @staticmethod
    def _coerce_int(value: object) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if math.isnan(value):
                return None
            return int(round(value))
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                return int(stripped)
            except ValueError:
                return None
        return None

    @staticmethod
    def _coerce_float(value: object) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            numeric = float(value)
            if math.isnan(numeric):
                return None
            return numeric
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                numeric = float(stripped)
                if math.isnan(numeric):
                    return None
                return numeric
            except ValueError:
                return None
        return None

    def _read_json(self, path: Path) -> Optional[dict]:
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except json.JSONDecodeError:
            logger.exception("Failed to parse JSON file %s", path)
            return None
