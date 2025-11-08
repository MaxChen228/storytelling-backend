"""Interactive CLI for the storytelling backend (Python implementation)."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Callable

import yaml
from storytelling_cli.status import ChapterStatus, natural_key, scan_chapters as status_scan_chapters
from storytelling_cli.table import build_chapter_table
from storytelling_cli.io import ConsoleIO
from storytelling_cli.services.chapters import ChapterService

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

    def __init__(self, io: Optional[ConsoleIO] = None) -> None:
        self.paths = self._load_paths()
        self.config = self._load_config()
        self.book_context: Optional[BookContext] = None
        self.use_color = sys.stdout.isatty()
        self.io = io or ConsoleIO(use_color=self.use_color, colorize_fn=colorize)
        self.chapter_service = ChapterService(
            repo_root=self.paths.repo_root,
            config_path=self.paths.config_path,
            io=self.io,
        )
        self.script_batch_size = max(1, SCRIPT_BATCH_SIZE_DEFAULT)
        self.script_batch_delay = max(0, SCRIPT_BATCH_DELAY_DEFAULT)
        self.audio_batch_size = max(1, AUDIO_BATCH_SIZE_DEFAULT)
        self.audio_batch_delay = max(0, AUDIO_BATCH_DELAY_DEFAULT)

    def _prompt_int(
        self,
        label: str,
        current: int,
        *,
        allow_zero: bool = False,
        color: str = "gray",
    ) -> int:
        while True:
            prompt_text = f"{label}（目前 {current}，Enter 保留）:\n> "
            try:
                raw = self.io.prompt(prompt_text, color=color).strip()
            except EOFError:
                return current
            if raw == "":
                return current
            try:
                value = int(raw)
            except ValueError:
                self.io.print(f"{ICON_WARNING} 請輸入整數。", color="yellow")
                continue
            if value < 0 or (value == 0 and not allow_zero):
                minimum = "0" if allow_zero else "1"
                self.io.print(f"{ICON_WARNING} 數值需大於等於 {minimum}。", color="yellow")
                continue
            return value

    def _prompt_yes_no(
        self,
        message: str,
        *,
        default: bool = False,
        color: str = "yellow",
    ) -> bool:
        suffix = " (Y/n)" if default else " (y/N)"
        try:
            response = self.io.prompt(f"{message}{suffix}\n> ", color=color).strip().lower()
        except EOFError:
            return default
        if not response:
            return default
        if response in {"y", "yes"}:
            return True
        if response in {"n", "no"}:
            return False
        self.io.print(f"{ICON_WARNING} 回覆僅支援 y 或 n。", color="yellow")
        return self._prompt_yes_no(message, default=default, color=color)

    def _update_env_file(self, updates: Dict[str, int]) -> None:
        env_path = self.paths.repo_root / ".env"
        backup_path = env_path.parent / f"{env_path.name}.bak"
        existing_lines: List[str] = []
        if env_path.exists():
            existing_lines = env_path.read_text(encoding="utf-8").splitlines()
            shutil.copy(env_path, backup_path)
        seen_keys = set()
        new_lines: List[str] = []
        for line in existing_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in line:
                new_lines.append(line)
                continue
            key, _, current_value = line.partition("=")
            normalized_key = key.strip()
            if normalized_key in updates:
                new_lines.append(f"{normalized_key}={updates[normalized_key]}")
                seen_keys.add(normalized_key)
            else:
                new_lines.append(line)
        for key, value in updates.items():
            if key not in seen_keys:
                new_lines.append(f"{key}={value}")
        content = "\n".join(new_lines).rstrip()
        env_path.write_text(content + ("\n" if content else ""), encoding="utf-8")
        self.io.print(f"{ICON_INFO} 已更新 .env 並備份至 {backup_path.name}", color="cyan")

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
                self.io.print(f"{ICON_WARNING} 在 {self.paths.books_root} 下找不到任何書籍章節", color="yellow")
                return False

            self.io.print()
            self.io.print("可用書籍：", color="cyan")
            self.io.print()
            for idx, book in enumerate(books):
                line = (
                    f"  [{idx}] {book['display_name']} "
                    f"(章節: {book['total_chapters']}, 已有摘要: {book['summary_count']})"
                )
                self.io.print(line, color="gray")
            self.io.print()
            choice = self.io.prompt("請輸入書籍索引（或 q 離開）：\n> ", color="white").strip()
            if choice.lower() == "q":
                if initial:
                    sys.exit(0)
                return False
            if not choice.isdigit():
                self.io.print(f"{ICON_MISSING} 無效的選擇", color="red")
                continue
            idx = int(choice)
            if not (0 <= idx < len(books)):
                self.io.print(f"{ICON_MISSING} 無效的選擇", color="red")
                continue
            book = books[idx]
            try:
                self.book_context = self.load_book_context(book["book_id"])
            except Exception as exc:  # pragma: no cover - interactive path
                self.io.print(f"{ICON_MISSING} {exc}", color="red")
                continue
            self.io.print()
            self.io.print(f"{ICON_BOOK} 已切換到「{self.book_context.display_name}」", color="green")
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
            self.io.print(f"{ICON_MISSING} 尚未選擇書籍", color="red")
            return

        outliers = self._timing_outliers(threshold)
        if not outliers:
            self.io.print(f"{ICON_INFO} 沒有任何字幕需修復 (門檻 {threshold:.1f}s)", color="cyan")
            return

        self.io.print(f"{ICON_INFO} 將修復以下字幕與音檔差值 > {threshold:.1f}s 的章節：", color="cyan")
        for status in outliers:
            gap_str = _format_gap_seconds(status.audio_subtitle_gap)
            self.io.print(f"  • {status.slug} (Δ {gap_str})", color="gray")
        self.io.print()

        successes: List[str] = []
        failures: List[Tuple[str, str]] = []
        for status in outliers:
            slug = status.slug
            try:
                ctx = self.book_context
                if not ctx:
                    raise RuntimeError("尚未選擇書籍")
                chapter_dir = ctx.book_output_dir / slug
                self.chapter_service.generate_script(ctx.book_id, slug)
                self.chapter_service.generate_audio(chapter_dir, slug, align=True)
                self.chapter_service.generate_subtitles(chapter_dir, slug)
                successes.append(slug)
            except Exception as exc:
                failures.append((slug, str(exc)))
                self.io.print(f"{ICON_MISSING} 章節 {slug} 修復失敗：{exc}", color="red")

        if successes:
            self.io.print(f"{ICON_COMPLETE} 修復完成的章節：{', '.join(successes)}", color="green")
        if failures:
            self.io.print(f"{ICON_WARNING} 修復失敗的章節：", color="yellow")
            for slug, message in failures:
                self.io.print(f"  • {slug} → {message}", color="yellow")
        self.io.print()

    # ---------------- Settings -----------------

    def configure_settings(self) -> None:
        while True:
            self.io.print()
            self.io.print("設定選單：", color="cyan")
            self.io.print("  1) 批次設定", color="white")
            self.io.print("  b) 返回主選單", color="gray")
            choice = self.io.prompt("> ", color="white").strip().lower()
            if choice == "1":
                self.configure_batch_settings()
                continue
            if choice in {"b", "back", "q"}:
                return
            self.io.print(f"{ICON_WARNING} 無效選項", color="yellow")

    def configure_batch_settings(self) -> None:
        changed = False
        while True:
            self.io.print()
            self.io.print("批次設定：", color="cyan")
            self.io.print(f"  1) 腳本批次大小：{self.script_batch_size}", color="white")
            self.io.print(f"  2) 腳本批次延遲（秒）：{self.script_batch_delay}", color="white")
            self.io.print(f"  3) 音頻批次大小：{self.audio_batch_size}", color="white")
            self.io.print(f"  4) 音頻批次延遲（秒）：{self.audio_batch_delay}", color="white")
            self.io.print("  r) 重設為預設值", color="gray")
            self.io.print("  s) 保存至 .env", color="gray")
            self.io.print("  b) 返回設定選單", color="gray")
            choice = self.io.prompt("> ", color="white").strip().lower()

            if choice == "1":
                new_value = self._prompt_int("輸入腳本批次大小", self.script_batch_size, allow_zero=False)
                if new_value != self.script_batch_size:
                    self.script_batch_size = max(1, new_value)
                    changed = True
                    self.io.print(f"{ICON_INFO} 腳本批次大小已更新為 {self.script_batch_size}", color="green")
                continue
            if choice == "2":
                new_value = self._prompt_int("輸入腳本批次延遲（秒）", self.script_batch_delay, allow_zero=True)
                if new_value != self.script_batch_delay:
                    self.script_batch_delay = max(0, new_value)
                    changed = True
                    self.io.print(f"{ICON_INFO} 腳本批次延遲已更新為 {self.script_batch_delay} 秒", color="green")
                continue
            if choice == "3":
                new_value = self._prompt_int("輸入音頻批次大小", self.audio_batch_size, allow_zero=False)
                if new_value != self.audio_batch_size:
                    self.audio_batch_size = max(1, new_value)
                    changed = True
                    self.io.print(f"{ICON_INFO} 音頻批次大小已更新為 {self.audio_batch_size}", color="green")
                continue
            if choice == "4":
                new_value = self._prompt_int("輸入音頻批次延遲（秒）", self.audio_batch_delay, allow_zero=True)
                if new_value != self.audio_batch_delay:
                    self.audio_batch_delay = max(0, new_value)
                    changed = True
                    self.io.print(f"{ICON_INFO} 音頻批次延遲已更新為 {self.audio_batch_delay} 秒", color="green")
                continue
            if choice == "r":
                self.script_batch_size = max(1, SCRIPT_BATCH_SIZE_DEFAULT)
                self.script_batch_delay = max(0, SCRIPT_BATCH_DELAY_DEFAULT)
                self.audio_batch_size = max(1, AUDIO_BATCH_SIZE_DEFAULT)
                self.audio_batch_delay = max(0, AUDIO_BATCH_DELAY_DEFAULT)
                changed = True
                self.io.print(f"{ICON_INFO} 已恢復為預設批次設定。", color="green")
                continue
            if choice == "s":
                updates = {
                    "PODCAST_SCRIPT_BATCH_SIZE": self.script_batch_size,
                    "PODCAST_SCRIPT_BATCH_DELAY": self.script_batch_delay,
                    "PODCAST_AUDIO_BATCH_SIZE": self.audio_batch_size,
                    "PODCAST_AUDIO_BATCH_DELAY": self.audio_batch_delay,
                }
                self._update_env_file(updates)
                continue
            if choice in {"b", "back", "q"}:
                if changed:
                    should_save = self._prompt_yes_no("是否將目前批次設定寫入 .env？")
                    if should_save:
                        updates = {
                            "PODCAST_SCRIPT_BATCH_SIZE": self.script_batch_size,
                            "PODCAST_SCRIPT_BATCH_DELAY": self.script_batch_delay,
                            "PODCAST_AUDIO_BATCH_SIZE": self.audio_batch_size,
                            "PODCAST_AUDIO_BATCH_DELAY": self.audio_batch_delay,
                        }
                        self._update_env_file(updates)
                return

            self.io.print(f"{ICON_WARNING} 無效選項", color="yellow")

    def display_chapters(self) -> None:
        statuses = self.scan_chapters()
        self.io.print()
        self.io.print(f"{ICON_BOOK} 書本：{self.book_context.display_name if self.book_context else '—'}", color="white")
        self.io.print()
        if not statuses:
            self.io.print(f"{ICON_WARNING} 尚未找到任何章節或源文件", color="yellow")
            self.io.print()
            return
        table_output = build_chapter_table(
            statuses,
            use_color=self.use_color,
            gap_threshold=1.5,
            colorize=colorize,
            format_gap=_format_gap_seconds,
            format_duration=_format_duration_mmss,
        )
        self.io.print(table_output)
        self.io.print()

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
            self.io.print(f"{ICON_WARNING} 沒有符合條件的章節可供 {purpose}", color="yellow")
            return []
        sorted_slugs = [status.slug for status in filtered]
        self.io.print("可處理章節（索引從 0 開始）：", color="white")
        for idx, slug in enumerate(sorted_slugs):
            self.io.print(f"  [{idx}] {slug}", color="gray")
        self.io.print()
        try:
            selection = self.io.prompt("請輸入章節範圍（如 0-5,7-9 或 all）：\n> ", color="cyan")
        except EOFError:
            return []
        try:
            return self._parse_selection(selection, sorted_slugs)
        except ValueError as exc:
            self.io.print(f"{ICON_MISSING} {exc}", color="red")
            return []

    # ---------------- Deletion helpers -----------------

    def _resolve_chapter_dir(self, slug: str) -> Path:
        ctx = self.book_context
        if not ctx:
            raise RuntimeError("尚未選擇書籍")
        return ctx.book_output_dir / slug

    def _preview_script(self, chapter: str, lines: int = 40) -> None:
        ctx = self.book_context
        if not ctx:
            self.io.print(f"{ICON_MISSING} 尚未選擇書籍", color="red")
            return
        script_path = ctx.book_output_dir / chapter / "podcast_script.txt"
        if not script_path.exists():
            self.io.print(f"{ICON_MISSING} 找不到腳本：{script_path}", color="red")
            return
        try:
            content = script_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = script_path.read_text(encoding="utf-8", errors="ignore")
        lines = max(1, lines)
        preview_lines = content.splitlines()[:lines]
        self.io.print()
        self.io.print(f"{ICON_SCRIPT} 腳本預覽：{chapter}", color="green")
        for idx, value in enumerate(preview_lines, start=1):
            self.io.print(f"{idx:>3}: {value}", color="gray")
        remaining = len(content.splitlines()) - len(preview_lines)
        if remaining > 0:
            self.io.print(f"… 其餘 {remaining} 行未顯示", color="gray")
        self.io.print()

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
            self.io.print(f"{ICON_WARNING} 沒有任何章節包含可刪除的{label}", color="yellow")
            return []
        self.io.print("可刪除的章節（索引從 0 開始）：", color="white")
        for idx, status in enumerate(available):
            self.io.print(f"  [{idx}] {status.slug}", color="gray")
        self.io.print()
        try:
            raw = self.io.prompt("請輸入章節索引（支援 0,3,5-7 或 all）：\n> ", color="cyan")
        except EOFError:
            return []
        sorted_slugs = [status.slug for status in available]
        try:
            return self._parse_selection(raw, sorted_slugs)
        except ValueError as exc:
            self.io.print(f"{ICON_MISSING} {exc}", color="red")
            return []

    def _artifact_handlers(self) -> Dict[str, Callable[[str], bool]]:
        ctx = self.book_context
        if not ctx:
            raise RuntimeError("尚未選擇書籍")
        return {
            "summary": lambda slug: self.chapter_service.delete_summary(
                ctx.summary_dir / f"{slug}{ctx.summary_suffix}", slug
            ),
            "script": lambda slug: self.chapter_service.delete_script(
                self._resolve_chapter_dir(slug), slug
            ),
            "audio": lambda slug: self.chapter_service.delete_audio(
                self._resolve_chapter_dir(slug), slug
            ),
            "subtitle": lambda slug: self.chapter_service.delete_subtitle(
                self._resolve_chapter_dir(slug), slug
            ),
        }

    def delete_artifact_menu(self) -> None:
        self.io.print("選擇刪除項目：", color="cyan")
        options = {"1": "summary", "2": "script", "3": "audio", "4": "subtitle"}
        for key, artifact in options.items():
            label = ARTIFACT_LABELS.get(artifact, artifact)
            self.io.print(f"  {key}) 刪除{label}", color="gray")
        self.io.print()
        choice = self.io.prompt("> ", color="white").strip()
        artifact = options.get(choice)
        if not artifact:
            self.io.print(f"{ICON_MISSING} 無效的選擇", color="red")
            return
        slugs = self._prompt_chapter_selection(artifact)
        if not slugs:
            return
        label = ARTIFACT_LABELS.get(artifact, artifact)
        targets_preview = ", ".join(slugs)
        confirm = self.io.prompt(
            f"確認刪除 {label}（{targets_preview}）？ (y/N)：\n> ", color="yellow"
        ).strip().lower()
        if confirm not in {"y", "yes"}:
            self.io.print(f"{ICON_WARNING} 已取消刪除", color="yellow")
            return
        handlers = self._artifact_handlers()
        handler = handlers.get(artifact)
        if not handler:
            self.io.print(f"{ICON_MISSING} 未支援的刪除類型：{artifact}", color="red")
            return
        for slug in slugs:
            handler(slug)

    def delete_artifact_cli(self, artifact: str, slug: str, *, assume_yes: bool = False) -> bool:
        artifact = artifact.lower()
        label = ARTIFACT_LABELS.get(artifact, artifact)
        if artifact not in ARTIFACT_LABELS:
            self.io.print(f"{ICON_MISSING} 未支援的刪除類型：{artifact}", color="red")
            return False
        available_slugs = {status.slug for status in self._available_chapters_for_artifact(artifact)}
        if slug not in available_slugs:
            # 允許直接檢查檔案是否存在（避免狀態表尚未刷新）
            if artifact != "summary" and not (self._resolve_chapter_dir(slug)).exists():
                self.io.print(f"{ICON_MISSING} 找不到章節：{slug}", color="red")
                return False
            if artifact == "summary":
                ctx = self.book_context
                if not ctx:
                    raise RuntimeError("尚未選擇書籍")
                summary_file = ctx.summary_dir / f"{slug}{ctx.summary_suffix}"
                if not summary_file.exists():
                    self.io.print(f"{ICON_MISSING} 找不到摘要：{slug}", color="red")
                    return False
        if not assume_yes:
            response = self.io.prompt(f"確認刪除 {label}（{slug}）？ (y/N)：\n> ", color="yellow").strip().lower()
            if response not in {"y", "yes"}:
                self.io.print(f"{ICON_WARNING} 已取消刪除", color="yellow")
                return False
        handler = self._artifact_handlers().get(artifact)
        if not handler:
            self.io.print(f"{ICON_MISSING} 未支援的刪除類型：{artifact}", color="red")
            return False
        return handler(slug)

    def _generate_summaries(self) -> None:
        ctx = self.book_context
        if not ctx:
            return
        start = self.io.prompt("輸入起始章節（1-based，預設 1）：\n> ", color="gray").strip()
        end = self.io.prompt("輸入結束章節（1-based，預設至最後一章，留空代表全部）：\n> ", color="gray").strip()
        force_choice = self.io.prompt("是否覆寫已存在摘要？ (y/N)：\n> ", color="gray").strip()

        self.chapter_service.generate_summaries(
            ctx.book_id,
            start,
            end,
            force_choice.lower() == "y",
        )

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
            self.io.print(f"{ICON_MISSING} 找不到音訊檔案：{chapter}", color="red")
            return
        subtitle = chapter_dir / "subtitles.srt"
        player_script = self.paths.repo_root / "play_with_subtitles.py"
        self.io.print(f"{ICON_PLAY} 播放：{chapter}", color="green")
        if subtitle.exists() and player_script.exists():
            self.chapter_service.run_command([sys.executable, str(player_script), str(audio), str(subtitle)])
            return
        if shutil.which("afplay"):
            subprocess.run(["afplay", str(audio)], check=True)
            return
        if shutil.which("ffplay"):
            subprocess.run(["ffplay", "-nodisp", "-autoexit", str(audio)], check=True)
            return
        self.io.print(f"{ICON_WARNING} 找不到播放器，請手動播放：{audio}", color="yellow")

    # ---------------- Batch executors -----------------

    # ---------------- Menu actions -----------------

    def batch_generate_scripts(self) -> None:
        if not self.book_context:
            self.io.print(f"{ICON_MISSING} 尚未選擇書籍", color="red")
            return
        chapters = self.chapter_range_prompt("生成腳本", "noscript", "requires_source")
        if not chapters:
            return
        ctx = self.book_context
        assert ctx is not None
        self.chapter_service.run_batch(
            chapters,
            self.script_batch_size,
            self.script_batch_delay,
            "腳本",
            lambda slug: self.chapter_service.generate_script(ctx.book_id, slug),
        )

    def batch_generate_audio(self) -> None:
        if not self.book_context:
            self.io.print(f"{ICON_MISSING} 尚未選擇書籍", color="red")
            return
        chapters = self.chapter_range_prompt("生成音頻", "noaudio", "requires_script")
        if not chapters:
            return
        ctx = self.book_context
        assert ctx is not None
        self.chapter_service.run_batch(
            chapters,
            self.audio_batch_size,
            self.audio_batch_delay,
            "音頻",
            lambda slug: self.chapter_service.generate_audio(ctx.book_output_dir / slug, slug),
        )

    def batch_generate_subtitles(self) -> None:
        if not self.book_context:
            self.io.print(f"{ICON_MISSING} 尚未選擇書籍", color="red")
            return
        chapters = self.chapter_range_prompt("生成字幕", "nosubtitle", "requires_script,requires_audio")
        if not chapters:
            return
        ctx = self.book_context
        assert ctx is not None
        self.chapter_service.run_serial(
            chapters,
            "字幕",
            lambda slug: self.chapter_service.generate_subtitles(ctx.book_output_dir / slug, slug),
        )

    def play_audio_menu(self) -> None:
        statuses = self.scan_chapters()
        if not statuses:
            self.io.print(f"{ICON_WARNING} 尚未找到章節", color="yellow")
            return
        selectable = [status for status in statuses if status.has_audio]
        if not selectable:
            self.io.print(f"{ICON_WARNING} 尚未生成任何音頻", color="yellow")
            return
        for idx, status in enumerate(selectable):
            self.io.print(f"  [{idx}] {status.slug}", color="gray")
        self.io.print()
        choice = self.io.prompt("請輸入章節索引：\n> ", color="white").strip()
        if not choice.isdigit():
            self.io.print(f"{ICON_MISSING} 無效的選擇", color="red")
            return
        idx = int(choice)
        if not (0 <= idx < len(selectable)):
            self.io.print(f"{ICON_MISSING} 無效的選擇", color="red")
            return
        chapter = selectable[idx].slug
        while True:
            self.io.print()
            self.io.print(f"選擇操作（{chapter}）：", color="cyan")
            self.io.print("  1) 查看腳本")
            self.io.print("  2) 播放音頻")
            self.io.print("  b) 返回")
            action = self.io.prompt("> ", color="white").strip().lower()
            if action in {"1", "script"}:
                self._preview_script(chapter)
                continue
            if action in {"2", "audio", "play"}:
                self._play_audio(chapter)
                break
            if action in {"b", "back", "q"}:
                break
            self.io.print(f"{ICON_WARNING} 無效選項", color="yellow")

    # ---------------- Main loop -----------------

    def main_menu(self) -> None:
        while True:
            self.display_chapters()
            self.io.print("操作選單：", color="cyan")
            self.io.print("  1) 生成腳本")
            self.io.print("  2) 生成音頻")
            self.io.print("  3) 生成字幕")
            self.io.print("  4) 生成摘要")
            self.io.print("  5) 播放音頻")
            self.io.print("  6) 刪除輸出")
            self.io.print("  7) 切換書籍")
            self.io.print("  8) 修復字幕時間差")
            self.io.print("  9) 設定")
            self.io.print("  r) 重新整理")
            self.io.print("  q) 離開")
            self.io.print()
            choice = self.io.prompt("> ", color="white").strip()
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
            elif choice == "9":
                self.configure_settings()
            elif choice.lower() == "r":
                continue
            elif choice.lower() == "q":
                self.io.print("再見！", color="cyan")
                sys.exit(0)
            else:
                self.io.print(f"{ICON_WARNING} 無效選項", color="yellow")

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
                cli.io.print(f"{ICON_MISSING} {exc}", color="red")
                sys.exit(1)
        else:
            if not cli.choose_book(initial=True):
                return
        if not cli.book_context:
            cli.io.print(f"{ICON_MISSING} 尚未選擇書籍", color="red")
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
