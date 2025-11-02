"""Interactive CLI for the storytelling backend (Python implementation)."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml
from storytelling_cli.status import ChapterStatus, natural_key, scan_chapters as status_scan_chapters
from storytelling_cli.table import build_chapter_table

# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

ICON_SCRIPT = "📝"
ICON_AUDIO = "🎵"
ICON_SUBTITLE = "🧾"
ICON_COMPLETE = "✅"
ICON_MISSING = "❌"
ICON_WARNING = "⚠️"
ICON_BOOK = "📚"
ICON_CHAPTER = "📖"
ICON_PLAY = "▶️"
ICON_SUMMARY = "🗒️"
ICON_ROCKET = "🚀"
ICON_HOURGLASS = "⏳"
ICON_INFO = "ℹ️"

COLOR_CODES = {
    "red": "\033[0;31m",
    "green": "\033[0;32m",
    "yellow": "\033[1;33m",
    "blue": "\033[0;34m",
    "purple": "\033[0;35m",
    "cyan": "\033[0;36m",
    "white": "\033[1;37m",
    "gray": "\033[0;90m",
    "reset": "\033[0m",
}

MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parent
CONFIG_PATH = REPO_ROOT / "podcast_config.yaml"

SCRIPT_BATCH_SIZE_DEFAULT = int(os.environ.get("PODCAST_SCRIPT_BATCH_SIZE", "10") or "10")
SCRIPT_BATCH_DELAY_DEFAULT = int(os.environ.get("PODCAST_SCRIPT_BATCH_DELAY", "10") or "10")
AUDIO_BATCH_SIZE_DEFAULT = int(os.environ.get("PODCAST_AUDIO_BATCH_SIZE", "5") or "5")
AUDIO_BATCH_DELAY_DEFAULT = int(os.environ.get("PODCAST_AUDIO_BATCH_DELAY", "60") or "60")


@dataclass
class Paths:
    """Resolved base paths from configuration."""

    repo_root: Path
    config_path: Path
    books_root: Path
    outputs_root: Path
    transcripts_root: Path


@dataclass
class BookContext:
    book_id: str
    display_name: str
    book_dir: Path
    summary_dir: Path
    summary_suffix: str
    book_output_dir: Path


ARTIFACT_LABELS = {
    "summary": "摘要",
    "script": "腳本",
    "audio": "音頻",
    "subtitle": "字幕",
}

ARTIFACT_CHOICES = tuple(ARTIFACT_LABELS.keys())


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def colorize(text: str, color: str, enabled: bool) -> str:
    if not enabled or color not in COLOR_CODES:
        return text
    return f"{COLOR_CODES[color]}{text}{COLOR_CODES['reset']}"


def _format_gap_seconds(value: Optional[float]) -> str:
    if value is None:
        return "—"
    sign = "+" if value >= 0 else "-"
    total = abs(value)
    minutes, seconds = divmod(total, 60)
    if minutes >= 1:
        return f"{sign}{int(minutes)}m{seconds:04.1f}s"
    return f"{sign}{seconds:.1f}s"


def _format_duration_mmss(value: float) -> str:
    total = max(0.0, value)
    minutes, seconds = divmod(total, 60)
    return f"({int(minutes):02d}:{int(seconds):02d})"


def resolve_path(base: Path, raw: str) -> Path:
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return candidate
    return (base / candidate).resolve()


# ---------------------------------------------------------------------------
# CLI implementation
# ---------------------------------------------------------------------------


class StorytellingCLI:
    """Interactive command-line interface for storytelling backend workflows."""

    def __init__(self) -> None:
        self.paths = self._load_paths()
        self.config = self._load_config()
        self.book_context: Optional[BookContext] = None
        self.use_color = sys.stdout.isatty()
        self.script_batch_size = max(1, SCRIPT_BATCH_SIZE_DEFAULT)
        self.script_batch_delay = max(0, SCRIPT_BATCH_DELAY_DEFAULT)
        self.audio_batch_size = max(1, AUDIO_BATCH_SIZE_DEFAULT)
        self.audio_batch_delay = max(0, AUDIO_BATCH_DELAY_DEFAULT)

    # ---------------- Configuration -----------------

    def _load_config(self) -> Dict[str, object]:
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(f"找不到配置檔案: {CONFIG_PATH}")
        with CONFIG_PATH.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    def _load_paths(self) -> Paths:
        config_dir = CONFIG_PATH.parent
        cfg = self._load_config()
        paths_cfg = cfg.get("paths", {}) if isinstance(cfg, dict) else {}
        books_root = resolve_path(config_dir, paths_cfg.get("books_root", "./data"))
        outputs_root = resolve_path(config_dir, paths_cfg.get("outputs_root", "./output"))
        transcripts_root = resolve_path(config_dir, paths_cfg.get("transcripts_root", "./data/transcripts"))
        return Paths(
            repo_root=REPO_ROOT,
            config_path=CONFIG_PATH,
            books_root=books_root,
            outputs_root=outputs_root,
            transcripts_root=transcripts_root,
        )

    # ---------------- Book selection -----------------

    def list_books(self) -> List[Dict[str, object]]:
        books_cfg = self.config.get("books", {}) if isinstance(self.config, dict) else {}
        defaults = books_cfg.get("defaults", {}) if isinstance(books_cfg, dict) else {}
        overrides_map = books_cfg.get("overrides", {}) if isinstance(books_cfg, dict) else {}

        books: List[Dict[str, object]] = []
        if not self.paths.books_root.exists():
            return books

        for child in sorted(self.paths.books_root.iterdir(), key=lambda p: p.name.lower()):
            if not child.is_dir():
                continue
            book_id = child.name
            overrides = overrides_map.get(book_id, {}) or {}
            merged = dict(defaults)
            merged.update(overrides)
            pattern = merged.get("file_pattern", "chapter*.txt")
            text_files = sorted(child.glob(pattern), key=lambda p: natural_key(p.stem))
            if not text_files:
                continue
            summary_dir = child / merged.get("summary_subdir", "summaries")
            summary_suffix = merged.get("summary_suffix", "_summary.txt")
            summary_count = 0
            if summary_dir.exists():
                summary_count = len(list(summary_dir.glob(f"*{summary_suffix}")))
            display_name = (
                merged.get("book_name")
                or overrides.get("display_name")
                or book_id
            )
            books.append(
                {
                    "book_id": book_id,
                    "display_name": display_name,
                    "total_chapters": len(text_files),
                    "summary_count": summary_count,
                }
            )
        return books

    def load_book_context(self, book_id: str) -> BookContext:
        books_cfg = self.config.get("books", {}) if isinstance(self.config, dict) else {}
        defaults = books_cfg.get("defaults", {}) if isinstance(books_cfg, dict) else {}
        overrides = (books_cfg.get("overrides", {}) if isinstance(books_cfg, dict) else {}).get(book_id, {}) or {}
        merged = dict(defaults)
        merged.update(overrides)

        book_dir = self.paths.books_root / book_id
        if not book_dir.exists():
            raise FileNotFoundError(f"找不到書籍目錄: {book_dir}")

        summary_dir = book_dir / merged.get("summary_subdir", "summaries")
        summary_dir.mkdir(parents=True, exist_ok=True)
        summary_suffix = merged.get("summary_suffix", "_summary.txt")

        display_name = (
            merged.get("book_name")
            or overrides.get("display_name")
            or book_id
        )

        output_name = (
            overrides.get("output_folder")
            or merged.get("book_name_override")
            or merged.get("book_name")
            or display_name
        )
        book_output_dir = self.paths.outputs_root / output_name
        book_output_dir.mkdir(parents=True, exist_ok=True)

        return BookContext(
            book_id=book_id,
            display_name=display_name,
            book_dir=book_dir,
            summary_dir=summary_dir,
            summary_suffix=summary_suffix,
            book_output_dir=book_output_dir,
        )

    def set_book_context(self, book_id: str) -> None:
        self.book_context = self.load_book_context(book_id)

    def choose_book(self, initial: bool = False) -> bool:
        while True:
            books = self.list_books()
            if not books:
                print(colorize(f"{ICON_WARNING} 在 {self.paths.books_root} 下找不到任何書籍章節", "yellow", self.use_color))
                return False

            print()
            print(colorize("可用書籍：", "cyan", self.use_color))
            print()
            for idx, book in enumerate(books):
                line = (
                    f"  [{idx}] {book['display_name']} "
                    f"(章節: {book['total_chapters']}, 已有摘要: {book['summary_count']})"
                )
                print(colorize(line, "gray", self.use_color))
            print()
            choice = input(colorize("請輸入書籍索引（或 q 離開）：\n> ", "white", self.use_color)).strip()
            if choice.lower() == "q":
                if initial:
                    sys.exit(0)
                return False
            if not choice.isdigit():
                print(colorize(f"{ICON_MISSING} 無效的選擇", "red", self.use_color))
                continue
            idx = int(choice)
            if not (0 <= idx < len(books)):
                print(colorize(f"{ICON_MISSING} 無效的選擇", "red", self.use_color))
                continue
            book = books[idx]
            try:
                self.book_context = self.load_book_context(book["book_id"])
            except Exception as exc:  # pragma: no cover - interactive path
                print(colorize(f"{ICON_MISSING} {exc}", "red", self.use_color))
                continue
            print()
            print(colorize(f"{ICON_BOOK} 已切換到「{self.book_context.display_name}」", "green", self.use_color))
            return True

    # ---------------- Chapter scanning -----------------

    def _timing_outliers(self, threshold: float = 1.5) -> List[ChapterStatus]:
        statuses = self.scan_chapters()
        return [status for status in statuses if status.audio_subtitle_gap is not None and status.audio_subtitle_gap > threshold]

    def scan_chapters(self) -> List[ChapterStatus]:
        if not self.book_context:
            return []
        ctx = self.book_context
        return status_scan_chapters(
            ctx.book_dir,
            ctx.summary_dir,
            ctx.summary_suffix,
            ctx.book_output_dir,
        )

    def repair_timing_outliers(self, threshold: float = 1.5) -> None:
        if not self.book_context:
            print(colorize(f"{ICON_MISSING} 尚未選擇書籍", "red", self.use_color))
            return

        outliers = self._timing_outliers(threshold)
        if not outliers:
            print(colorize(f"{ICON_INFO} 沒有任何字幕需修復 (門檻 {threshold:.1f}s)", "cyan", self.use_color))
            return

        print(colorize(f"{ICON_INFO} 將修復以下字幕與音檔差值 > {threshold:.1f}s 的章節：", "cyan", self.use_color))
        for status in outliers:
            gap_str = _format_gap_seconds(status.audio_subtitle_gap)
            print(colorize(f"  • {status.slug} (Δ {gap_str})", "gray", self.use_color))
        print()

        successes: List[str] = []
        failures: List[Tuple[str, str]] = []
        for status in outliers:
            slug = status.slug
            try:
                self._generate_script(slug)
                self._generate_audio(slug, align=True)
                self._generate_subtitles(slug)
                successes.append(slug)
            except Exception as exc:
                failures.append((slug, str(exc)))
                print(colorize(f"{ICON_MISSING} 章節 {slug} 修復失敗：{exc}", "red", self.use_color))

        if successes:
            print(colorize(f"{ICON_COMPLETE} 修復完成的章節：{', '.join(successes)}", "green", self.use_color))
        if failures:
            print(colorize(f"{ICON_WARNING} 修復失敗的章節：", "yellow", self.use_color))
            for slug, message in failures:
                print(colorize(f"  • {slug} → {message}", "yellow", self.use_color))
        print()
    def display_chapters(self) -> None:
        statuses = self.scan_chapters()
        print()
        print(colorize(f"{ICON_BOOK} 書本：{self.book_context.display_name if self.book_context else '—'}", "white", self.use_color))
        print()
        if not statuses:
            print(colorize(f"{ICON_WARNING} 尚未找到任何章節或源文件", "yellow", self.use_color))
            print()
            return
        table_output = build_chapter_table(
            statuses,
            use_color=self.use_color,
            gap_threshold=1.5,
            colorize=colorize,
            format_gap=_format_gap_seconds,
            format_duration=_format_duration_mmss,
        )
        print(table_output)
        print()

    # ---------------- Selection helpers -----------------

    def _filter_chapters(self, statuses: List[ChapterStatus], required: str, optional: str) -> List[ChapterStatus]:
        def matches_required(status: ChapterStatus) -> bool:
            mapping = {
                "source": status.has_source,
                "summary": status.has_summary,
                "nosummary": not status.has_summary,
                "script": status.has_script,
                "noscript": not status.has_script,
                "audio": status.has_audio,
                "noaudio": not status.has_audio,
                "subtitle": status.has_subtitle,
                "nosubtitle": not status.has_subtitle,
                "": True,
                None: True,
            }
            return mapping.get(required, True)

        def satisfies_optional(status: ChapterStatus) -> bool:
            if not optional:
                return True
            for item in optional.split(","):
                item = item.strip()
                if not item:
                    continue
                if item == "requires_source" and not status.has_source:
                    return False
                if item == "requires_summary" and not status.has_summary:
                    return False
                if item == "requires_script" and not status.has_script:
                    return False
                if item == "requires_audio" and not status.has_audio:
                    return False
                if item == "requires_subtitle" and not status.has_subtitle:
                    return False
            return True

        return [status for status in statuses if matches_required(status) and satisfies_optional(status)]

    def _parse_selection(self, selection: str, candidates: List[str]) -> List[str]:
        selection = selection.strip()
        if not selection:
            raise ValueError("未輸入任何章節")
        if selection.lower() in {"all", "a"}:
            return list(candidates)

        chosen: List[str] = []
        seen = set()
        parts = [part.strip() for part in selection.split(",") if part.strip()]
        for part in parts:
            if part.isdigit():
                idx = int(part)
                if not (0 <= idx < len(candidates)):
                    raise ValueError(f"索引 {idx} 超出範圍 (0-{len(candidates) - 1})")
                slug = candidates[idx]
                if slug not in seen:
                    chosen.append(slug)
                    seen.add(slug)
                continue
            range_match = re.match(r"^(\d+)-(\d+)$", part)
            if range_match:
                start, end = int(range_match.group(1)), int(range_match.group(2))
                if start > end:
                    start, end = end, start
                for idx in range(start, end + 1):
                    if 0 <= idx < len(candidates):
                        slug = candidates[idx]
                        if slug not in seen:
                            chosen.append(slug)
                            seen.add(slug)
                continue
            if part in candidates:
                if part not in seen:
                    chosen.append(part)
                    seen.add(part)
                continue
            raise ValueError(f"無效的章節或範圍 '{part}'")
        if not chosen:
            raise ValueError("沒有匹配的章節")
        return chosen

    def chapter_range_prompt(self, purpose: str, required: str, optional: str = "") -> List[str]:
        statuses = self.scan_chapters()
        filtered = self._filter_chapters(statuses, required, optional)
        if not filtered:
            print(colorize(f"{ICON_WARNING} 沒有符合條件的章節可供 {purpose}", "yellow", self.use_color))
            return []
        sorted_slugs = [status.slug for status in filtered]
        print(colorize("可處理章節（索引從 0 開始）：", "white", self.use_color))
        for idx, slug in enumerate(sorted_slugs):
            print(colorize(f"  [{idx}] {slug}", "gray", self.use_color))
        print()
        try:
            selection = input(colorize("請輸入章節範圍（如 0-5,7-9 或 all）：\n> ", "cyan", self.use_color))
        except EOFError:
            return []
        try:
            return self._parse_selection(selection, sorted_slugs)
        except ValueError as exc:
            print(colorize(f"{ICON_MISSING} {exc}", "red", self.use_color))
            return []

    # ---------------- Deletion helpers -----------------

    def _load_json_file(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(colorize(f"{ICON_WARNING} 解析 JSON 失敗：{path}", "yellow", self.use_color))
            return {}

    def _write_json_file(self, path: Path, payload: Dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _resolve_chapter_dir(self, slug: str) -> Path:
        ctx = self.book_context
        if not ctx:
            raise RuntimeError("尚未選擇書籍")
        return ctx.book_output_dir / slug

    def _preview_script(self, chapter: str, lines: int = 40) -> None:
        ctx = self.book_context
        if not ctx:
            print(colorize(f"{ICON_MISSING} 尚未選擇書籍", "red", self.use_color))
            return
        script_path = ctx.book_output_dir / chapter / "podcast_script.txt"
        if not script_path.exists():
            print(colorize(f"{ICON_MISSING} 找不到腳本：{script_path}", "red", self.use_color))
            return
        try:
            content = script_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = script_path.read_text(encoding="utf-8", errors="ignore")
        lines = max(1, lines)
        preview_lines = content.splitlines()[:lines]
        print()
        print(colorize(f"{ICON_SCRIPT} 腳本預覽：{chapter}", "green", self.use_color))
        for idx, value in enumerate(preview_lines, start=1):
            print(colorize(f"{idx:>3}: {value}", "gray", self.use_color))
        remaining = len(content.splitlines()) - len(preview_lines)
        if remaining > 0:
            print(colorize(f"… 其餘 {remaining} 行未顯示", "gray", self.use_color))
        print()

    def _available_chapters_for_artifact(self, artifact: str) -> List[ChapterStatus]:
        predicate_map = {
            "summary": lambda status: status.has_summary,
            "script": lambda status: status.has_script,
            "audio": lambda status: status.has_audio,
            "subtitle": lambda status: status.has_subtitle,
        }
        predicate = predicate_map.get(artifact)
        if not predicate:
            return []
        return [status for status in self.scan_chapters() if predicate(status)]

    def _prompt_chapter_selection(self, artifact: str) -> List[str]:
        available = self._available_chapters_for_artifact(artifact)
        label = ARTIFACT_LABELS.get(artifact, artifact)
        if not available:
            print(colorize(f"{ICON_WARNING} 沒有任何章節包含可刪除的{label}", "yellow", self.use_color))
            return []
        print(colorize("可刪除的章節（索引從 0 開始）：", "white", self.use_color))
        for idx, status in enumerate(available):
            print(colorize(f"  [{idx}] {status.slug}", "gray", self.use_color))
        print()
        try:
            raw = input(colorize("請輸入章節索引（支援 0,3,5-7 或 all）：\n> ", "cyan", self.use_color))
        except EOFError:
            return []
        sorted_slugs = [status.slug for status in available]
        try:
            return self._parse_selection(raw, sorted_slugs)
        except ValueError as exc:
            print(colorize(f"{ICON_MISSING} {exc}", "red", self.use_color))
            return []

    def _delete_summary(self, slug: str) -> bool:
        ctx = self.book_context
        if not ctx:
            raise RuntimeError("尚未選擇書籍")
        summary_file = ctx.summary_dir / f"{slug}{ctx.summary_suffix}"
        if not summary_file.exists():
            print(colorize(f"{ICON_MISSING} 找不到摘要：{summary_file}", "red", self.use_color))
            return False
        summary_file.unlink()
        print(colorize(f"{ICON_COMPLETE} 已刪除摘要：{slug}", "green", self.use_color))
        return True

    def _delete_script(self, slug: str) -> bool:
        chapter_dir = self._resolve_chapter_dir(slug)
        candidates = [chapter_dir / "podcast_script.txt", chapter_dir / "script.txt"]
        removed = False
        for candidate in candidates:
            if candidate.exists():
                candidate.unlink()
                removed = True
        if not removed:
            print(colorize(f"{ICON_MISSING} 找不到腳本：{chapter_dir}", "red", self.use_color))
            return False
        print(colorize(f"{ICON_COMPLETE} 已刪除腳本：{slug}", "green", self.use_color))
        return True

    def _delete_audio(self, slug: str) -> bool:
        chapter_dir = self._resolve_chapter_dir(slug)
        patterns = ["podcast.wav", "podcast.mp3"]
        removed_files: List[Path] = []
        for pattern in patterns:
            target = chapter_dir / pattern
            if target.exists():
                target.unlink()
                removed_files.append(target)
        for extra in list(chapter_dir.glob("podcast_part*.wav")) + list(chapter_dir.glob("podcast_part*.mp3")):
            if extra.exists():
                extra.unlink()
                removed_files.append(extra)
        audio_meta = chapter_dir / "audio_metadata.json"
        if audio_meta.exists():
            audio_meta.unlink()
            removed_files.append(audio_meta)
        if not removed_files:
            print(colorize(f"{ICON_MISSING} 找不到音頻檔案：{chapter_dir}", "red", self.use_color))
            return False

        metadata_path = chapter_dir / "metadata.json"
        metadata = self._load_json_file(metadata_path)
        if metadata.get("audio_file"):
            metadata["audio_file"] = None
            self._write_json_file(metadata_path, metadata)

        print(colorize(f"{ICON_COMPLETE} 已刪除音頻：{slug}", "green", self.use_color))
        return True

    def _delete_subtitle(self, slug: str) -> bool:
        chapter_dir = self._resolve_chapter_dir(slug)
        subtitle_file = chapter_dir / "subtitles.srt"
        aligned_json = chapter_dir / "aligned_transcript.json"
        removed = False
        for target in (subtitle_file, aligned_json):
            if target.exists():
                target.unlink()
                removed = True
        if not removed:
            print(colorize(f"{ICON_MISSING} 找不到字幕：{chapter_dir}", "red", self.use_color))
            return False

        metadata_path = chapter_dir / "metadata.json"
        metadata = self._load_json_file(metadata_path)
        keys_to_remove = [key for key in list(metadata.keys()) if key.startswith("alignment_")]
        changed = False
        for key in keys_to_remove:
            metadata.pop(key, None)
            changed = True
        if changed:
            self._write_json_file(metadata_path, metadata)

        audio_meta_path = chapter_dir / "audio_metadata.json"
        audio_metadata = self._load_json_file(audio_meta_path)
        audio_keys = [key for key in list(audio_metadata.keys()) if key.startswith("alignment_")]
        audio_changed = False
        for key in audio_keys:
            audio_metadata.pop(key, None)
            audio_changed = True
        if audio_changed:
            self._write_json_file(audio_meta_path, audio_metadata)

        print(colorize(f"{ICON_COMPLETE} 已刪除字幕：{slug}", "green", self.use_color))
        return True

    def _delete_artifact(self, artifact: str, slug: str) -> bool:
        handlers = {
            "summary": self._delete_summary,
            "script": self._delete_script,
            "audio": self._delete_audio,
            "subtitle": self._delete_subtitle,
        }
        handler = handlers.get(artifact)
        if not handler:
            print(colorize(f"{ICON_MISSING} 未支援的刪除類型：{artifact}", "red", self.use_color))
            return False
        return handler(slug)

    def delete_artifact_menu(self) -> None:
        print(colorize("選擇刪除項目：", "cyan", self.use_color))
        options = {"1": "summary", "2": "script", "3": "audio", "4": "subtitle"}
        for key, artifact in options.items():
            label = ARTIFACT_LABELS.get(artifact, artifact)
            print(colorize(f"  {key}) 刪除{label}", "gray", self.use_color))
        print()
        choice = input(colorize("> ", "white", self.use_color)).strip()
        artifact = options.get(choice)
        if not artifact:
            print(colorize(f"{ICON_MISSING} 無效的選擇", "red", self.use_color))
            return
        slugs = self._prompt_chapter_selection(artifact)
        if not slugs:
            return
        label = ARTIFACT_LABELS.get(artifact, artifact)
        targets_preview = ", ".join(slugs)
        confirm = input(
            colorize(f"確認刪除 {label}（{targets_preview}）？ (y/N)：\n> ", "yellow", self.use_color)
        ).strip().lower()
        if confirm not in {"y", "yes"}:
            print(colorize(f"{ICON_WARNING} 已取消刪除", "yellow", self.use_color))
            return
        for slug in slugs:
            self._delete_artifact(artifact, slug)

    def delete_artifact_cli(self, artifact: str, slug: str, *, assume_yes: bool = False) -> bool:
        artifact = artifact.lower()
        label = ARTIFACT_LABELS.get(artifact, artifact)
        if artifact not in ARTIFACT_LABELS:
            print(colorize(f"{ICON_MISSING} 未支援的刪除類型：{artifact}", "red", self.use_color))
            return False
        available_slugs = {status.slug for status in self._available_chapters_for_artifact(artifact)}
        if slug not in available_slugs:
            # 允許直接檢查檔案是否存在（避免狀態表尚未刷新）
            if artifact != "summary" and not (self._resolve_chapter_dir(slug)).exists():
                print(colorize(f"{ICON_MISSING} 找不到章節：{slug}", "red", self.use_color))
                return False
            if artifact == "summary":
                ctx = self.book_context
                if not ctx:
                    raise RuntimeError("尚未選擇書籍")
                summary_file = ctx.summary_dir / f"{slug}{ctx.summary_suffix}"
                if not summary_file.exists():
                    print(colorize(f"{ICON_MISSING} 找不到摘要：{slug}", "red", self.use_color))
                    return False
        if not assume_yes:
            response = input(colorize(f"確認刪除 {label}（{slug}）？ (y/N)：\n> ", "yellow", self.use_color)).strip().lower()
            if response not in {"y", "yes"}:
                print(colorize(f"{ICON_WARNING} 已取消刪除", "yellow", self.use_color))
                return False
        return self._delete_artifact(artifact, slug)

    # ---------------- Subprocess helpers -----------------

    def _run_subprocess(self, args: Sequence[str]) -> None:
        subprocess.run(
            list(args),
            check=True,
            cwd=str(self.paths.repo_root),
        )

    def _generate_script(self, chapter: str) -> None:
        ctx = self.book_context
        if not ctx:
            raise RuntimeError("尚未選擇書籍")
        print(colorize(f"{ICON_SCRIPT} 生成腳本：{chapter}", "green", self.use_color))
        self._run_subprocess(
            [
                sys.executable,
                "generate_script.py",
                chapter,
                "--config",
                str(self.paths.config_path),
                "--book-id",
                ctx.book_id,
            ]
        )
        print(colorize(f"{ICON_COMPLETE} 腳本完成：{chapter}", "green", self.use_color))

    def _generate_audio(self, chapter: str, align: bool = False) -> None:
        ctx = self.book_context
        if not ctx:
            raise RuntimeError("尚未選擇書籍")
        script_file = ctx.book_output_dir / chapter / "podcast_script.txt"
        if not script_file.exists():
            raise FileNotFoundError(f"{chapter} 尚未生成腳本")
        print(colorize(f"{ICON_AUDIO} 生成音頻：{chapter}", "green", self.use_color))
        args = [
            sys.executable,
            "generate_audio.py",
            str(ctx.book_output_dir / chapter),
            "--config",
            str(self.paths.config_path),
        ]
        if align:
            args.append("--align")
        self._run_subprocess(args)
        print(colorize(f"{ICON_COMPLETE} 音頻完成：{chapter}", "green", self.use_color))

    def _generate_subtitles(self, chapter: str) -> None:
        ctx = self.book_context
        if not ctx:
            raise RuntimeError("尚未選擇書籍")
        chapter_dir = ctx.book_output_dir / chapter
        script_file = chapter_dir / "podcast_script.txt"
        audio_wav = chapter_dir / "podcast.wav"
        audio_mp3 = chapter_dir / "podcast.mp3"
        if not script_file.exists():
            raise FileNotFoundError(f"{chapter} 尚未生成腳本")
        if not audio_wav.exists() and not audio_mp3.exists():
            raise FileNotFoundError(f"{chapter} 尚未生成音頻")
        print(colorize(f"{ICON_SUBTITLE} 生成字幕：{chapter}", "green", self.use_color))
        self._run_subprocess(
            [
                sys.executable,
                "generate_subtitles.py",
                str(chapter_dir),
                "--config",
                str(self.paths.config_path),
            ]
        )
        print(colorize(f"{ICON_COMPLETE} 字幕完成：{chapter}", "green", self.use_color))

    def _generate_summaries(self) -> None:
        ctx = self.book_context
        if not ctx:
            return
        print(colorize(f"{ICON_SUMMARY} 生成摘要", "cyan", self.use_color))
        start = input(colorize("輸入起始章節（1-based，預設 1）：\n> ", "gray", self.use_color)).strip()
        end = input(colorize("輸入結束章節（1-based，預設至最後一章，留空代表全部）：\n> ", "gray", self.use_color)).strip()
        force_choice = input(colorize("是否覆寫已存在摘要？ (y/N)：\n> ", "gray", self.use_color)).strip()

        args = [
            sys.executable,
            "preprocess_chapters.py",
            "--config",
            str(self.paths.config_path),
            "--book-id",
            ctx.book_id,
        ]
        if start.isdigit():
            args.extend(["--start-chapter", start])
        if end.isdigit():
            args.extend(["--end-chapter", end])
        if force_choice.lower() == "y":
            args.append("--force")

        print(colorize(f"{ICON_INFO} 命令：{' '.join(args)}", "gray", self.use_color))
        self._run_subprocess(args)

    def _play_audio(self, chapter: str) -> None:
        ctx = self.book_context
        if not ctx:
            return
        chapter_dir = ctx.book_output_dir / chapter
        audio = None
        if (chapter_dir / "podcast.wav").exists():
            audio = chapter_dir / "podcast.wav"
        elif (chapter_dir / "podcast.mp3").exists():
            audio = chapter_dir / "podcast.mp3"
        if not audio:
            print(colorize(f"{ICON_MISSING} 找不到音訊檔案：{chapter}", "red", self.use_color))
            return
        subtitle = chapter_dir / "subtitles.srt"
        player_script = self.paths.repo_root / "play_with_subtitles.py"
        print(colorize(f"{ICON_PLAY} 播放：{chapter}", "green", self.use_color))
        if subtitle.exists() and player_script.exists():
            self._run_subprocess([sys.executable, str(player_script), str(audio), str(subtitle)])
            return
        if shutil.which("afplay"):
            subprocess.run(["afplay", str(audio)], check=True)
            return
        if shutil.which("ffplay"):
            subprocess.run(["ffplay", "-nodisp", "-autoexit", str(audio)], check=True)
            return
        print(colorize(f"{ICON_WARNING} 找不到播放器，請手動播放：{audio}", "yellow", self.use_color))

    # ---------------- Batch executors -----------------

    def _run_batch(self, chapters: List[str], batch_size: int, delay: int, label: str, worker) -> None:
        total = len(chapters)
        total_batches = (total + batch_size - 1) // batch_size
        print()
        print(colorize(f"共 {total} 章節，{label}批次大小 {batch_size}，共 {total_batches} 批。", "white", self.use_color))
        start = 0
        batch_index = 1
        failures: List[str] = []
        while start < total:
            chunk = chapters[start : start + batch_size]
            print()
            print(colorize(f"{label}批次 {batch_index}/{total_batches}", "cyan", self.use_color))
            for slug in chunk:
                print(colorize(f"  {slug}", "white", self.use_color))
            print()
            print(colorize(f"{ICON_ROCKET} 並行執行 {len(chunk)} 個任務...", "gray", self.use_color))
            with ThreadPoolExecutor(max_workers=len(chunk)) as executor:
                future_map = {executor.submit(worker, slug): slug for slug in chunk}
                for future in as_completed(future_map):
                    slug = future_map[future]
                    try:
                        future.result()
                    except subprocess.CalledProcessError:
                        failures.append(slug)
                        print(colorize(f"{ICON_MISSING} 任務失敗：{slug}", "red", self.use_color))
                    except Exception as exc:  # pragma: no cover - unexpected path
                        failures.append(slug)
                        print(colorize(f"{ICON_MISSING} 任務失敗：{slug} ({exc})", "red", self.use_color))
            start += len(chunk)
            batch_index += 1
            if start < total and delay > 0:
                print()
                print(colorize(f"{ICON_HOURGLASS} 等待 {delay} 秒後處理下一批{label}...", "gray", self.use_color))
                time.sleep(delay)
        if failures:
            print()
            print(colorize(f"{ICON_WARNING} 部分 {label} 批次失敗：{', '.join(failures)}", "yellow", self.use_color))
        else:
            print()
            print(colorize(f"{ICON_COMPLETE} 全部 {label} 任務完成", "green", self.use_color))

    # ---------------- Menu actions -----------------

    def batch_generate_scripts(self) -> None:
        chapters = self.chapter_range_prompt("生成腳本", "noscript", "requires_source")
        if not chapters:
            return
        self._run_batch(chapters, self.script_batch_size, self.script_batch_delay, "腳本", self._generate_script)

    def batch_generate_audio(self) -> None:
        chapters = self.chapter_range_prompt("生成音頻", "noaudio", "requires_script")
        if not chapters:
            return
        self._run_batch(chapters, self.audio_batch_size, self.audio_batch_delay, "音頻", self._generate_audio)

    def batch_generate_subtitles(self) -> None:
        chapters = self.chapter_range_prompt("生成字幕", "nosubtitle", "requires_script,requires_audio")
        if not chapters:
            return
        for chapter in chapters:
            try:
                self._generate_subtitles(chapter)
            except Exception as exc:  # pragma: no cover - interactive path
                print(colorize(f"{ICON_MISSING} 字幕生成失敗：{chapter} ({exc})", "red", self.use_color))

    def play_audio_menu(self) -> None:
        statuses = self.scan_chapters()
        if not statuses:
            print(colorize(f"{ICON_WARNING} 尚未找到章節", "yellow", self.use_color))
            return
        selectable = [status for status in statuses if status.has_audio]
        if not selectable:
            print(colorize(f"{ICON_WARNING} 尚未生成任何音頻", "yellow", self.use_color))
            return
        for idx, status in enumerate(selectable):
            print(colorize(f"  [{idx}] {status.slug}", "gray", self.use_color))
        print()
        choice = input(colorize("請輸入章節索引：\n> ", "white", self.use_color)).strip()
        if not choice.isdigit():
            print(colorize(f"{ICON_MISSING} 無效的選擇", "red", self.use_color))
            return
        idx = int(choice)
        if not (0 <= idx < len(selectable)):
            print(colorize(f"{ICON_MISSING} 無效的選擇", "red", self.use_color))
            return
        chapter = selectable[idx].slug
        while True:
            print()
            print(colorize(f"選擇操作（{chapter}）：", "cyan", self.use_color))
            print("  1) 查看腳本")
            print("  2) 播放音頻")
            print("  b) 返回")
            action = input(colorize("> ", "white", self.use_color)).strip().lower()
            if action in {"1", "script"}:
                self._preview_script(chapter)
                continue
            if action in {"2", "audio", "play"}:
                self._play_audio(chapter)
                break
            if action in {"b", "back", "q"}:
                break
            print(colorize(f"{ICON_WARNING} 無效選項", "yellow", self.use_color))

    # ---------------- Main loop -----------------

    def main_menu(self) -> None:
        while True:
            self.display_chapters()
            print(colorize("操作選單：", "cyan", self.use_color))
            print("  1) 生成腳本")
            print("  2) 生成音頻")
            print("  3) 生成字幕")
            print("  4) 生成摘要")
            print("  5) 播放音頻")
            print("  6) 刪除輸出")
            print("  7) 切換書籍")
            print("  8) 修復字幕時間差")
            print("  r) 重新整理")
            print("  q) 離開")
            print()
            choice = input(
                colorize(
                    "> ", "white", self.use_color
                )
            ).strip()
            if choice == "1":
                self.batch_generate_scripts()
            elif choice == "2":
                self.batch_generate_audio()
            elif choice == "3":
                self.batch_generate_subtitles()
            elif choice == "4":
                self._generate_summaries()
            elif choice == "5":
                self.play_audio_menu()
            elif choice == "6":
                self.delete_artifact_menu()
            elif choice == "7":
                if not self.choose_book():
                    continue
            elif choice == "8":
                self.repair_timing_outliers()
            elif choice.lower() == "r":
                continue
            elif choice.lower() == "q":
                print(colorize("再見！", "cyan", self.use_color))
                sys.exit(0)
            else:
                print(colorize(f"{ICON_WARNING} 無效選項", "yellow", self.use_color))

def parse_cli_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Storytelling CLI")
    subparsers = parser.add_subparsers(dest="command")

    delete_parser = subparsers.add_parser("delete", help="刪除指定章節的輸出")
    delete_parser.add_argument("artifact", choices=ARTIFACT_CHOICES, help="要刪除的類型")
    delete_parser.add_argument("chapter", help="章節 slug，如 chapter12")
    delete_parser.add_argument("--book-id", dest="book_id", help="指定書籍 ID（預設會開啟互動選擇）")
    delete_parser.add_argument("--yes", dest="assume_yes", action="store_true", help="跳過刪除確認")

    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_cli_args(argv)
    cli = StorytellingCLI()

    if getattr(args, "command", None) == "delete":
        book_id = getattr(args, "book_id", None)
        if book_id:
            try:
                cli.set_book_context(book_id)
            except Exception as exc:  # pragma: no cover - interactive path
                print(colorize(f"{ICON_MISSING} {exc}", "red", cli.use_color))
                sys.exit(1)
        else:
            if not cli.choose_book(initial=True):
                return
        if not cli.book_context:
            print(colorize(f"{ICON_MISSING} 尚未選擇書籍", "red", cli.use_color))
            sys.exit(1)
        success = cli.delete_artifact_cli(args.artifact, args.chapter, assume_yes=getattr(args, "assume_yes", False))
        if not success:
            sys.exit(1)
        return

    if not cli.choose_book(initial=True):
        return
    cli.main_menu()


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
