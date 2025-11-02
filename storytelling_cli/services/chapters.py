"""Services for chapter-related operations in the storytelling CLI."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Sequence

from storytelling_cli.io import ConsoleIO

BatchWorker = Callable[[str], None]


@dataclass
class ChapterService:
    """Encapsulates generation, deletion, and batch utilities for chapters."""

    repo_root: Path
    config_path: Path
    io: ConsoleIO

    def _run_subprocess(self, args: Sequence[str]) -> None:
        subprocess.run(list(args), check=True, cwd=str(self.repo_root))

    def run_command(self, args: Sequence[str]) -> None:
        self._run_subprocess(args)

    # ------------------------------------------------------------------ Generation
    def generate_script(self, book_id: str, chapter: str) -> None:
        self.io.print(f"📝 生成腳本：{chapter}", color="green")
        self._run_subprocess(
            [
                sys.executable,
                "generate_script.py",
                chapter,
                "--config",
                str(self.config_path),
                "--book-id",
                book_id,
            ]
        )
        self.io.print(f"✅ 腳本完成：{chapter}", color="green")

    def generate_audio(self, chapter_dir: Path, chapter: str, align: bool = False) -> None:
        script_file = chapter_dir / "podcast_script.txt"
        if not script_file.exists():
            raise FileNotFoundError(f"{chapter} 尚未生成腳本")

        self.io.print(f"🎵 生成音頻：{chapter}", color="green")
        args = [
            sys.executable,
            "generate_audio.py",
            str(chapter_dir),
            "--config",
            str(self.config_path),
        ]
        if align:
            args.append("--align")
        self._run_subprocess(args)
        self.io.print(f"✅ 音頻完成：{chapter}", color="green")

    def generate_subtitles(self, chapter_dir: Path, chapter: str) -> None:
        script_file = chapter_dir / "podcast_script.txt"
        audio_wav = chapter_dir / "podcast.wav"
        audio_mp3 = chapter_dir / "podcast.mp3"
        if not script_file.exists():
            raise FileNotFoundError(f"{chapter} 尚未生成腳本")
        if not audio_wav.exists() and not audio_mp3.exists():
            raise FileNotFoundError(f"{chapter} 尚未生成音頻")

        self.io.print(f"🧾 生成字幕：{chapter}", color="green")
        self._run_subprocess(
            [
                sys.executable,
                "generate_subtitles.py",
                str(chapter_dir),
                "--config",
                str(self.config_path),
            ]
        )
        self.io.print(f"✅ 字幕完成：{chapter}", color="green")

    def generate_summaries(
        self,
        book_id: str,
        start: str,
        end: str,
        force: bool,
    ) -> None:
        args = [
            sys.executable,
            "preprocess_chapters.py",
            "--config",
            str(self.config_path),
            "--book-id",
            book_id,
        ]
        if start.isdigit():
            args.extend(["--start-chapter", start])
        if end.isdigit():
            args.extend(["--end-chapter", end])
        if force:
            args.append("--force")

        self.io.print(f"🗒️ 生成摘要", color="cyan")
        self.io.print(f"ℹ️ 命令：{' '.join(args)}", color="gray")
        self._run_subprocess(args)

    # ------------------------------------------------------------------ Deletion helpers
    def delete_summary(self, summary_file: Path, slug: str) -> bool:
        if not summary_file.exists():
            self.io.print(f"❌ 找不到摘要：{summary_file}", color="red")
            return False
        summary_file.unlink()
        self.io.print(f"✅ 已刪除摘要：{slug}", color="green")
        return True

    def delete_script(self, chapter_dir: Path, slug: str) -> bool:
        candidates = [chapter_dir / "podcast_script.txt", chapter_dir / "script.txt"]
        removed = False
        for candidate in candidates:
            if candidate.exists():
                candidate.unlink()
                removed = True
        if not removed:
            self.io.print(f"❌ 找不到腳本：{chapter_dir}", color="red")
            return False
        self.io.print(f"✅ 已刪除腳本：{slug}", color="green")
        return True

    def delete_audio(self, chapter_dir: Path, slug: str) -> bool:
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
            self.io.print(f"❌ 找不到音頻檔案：{chapter_dir}", color="red")
            return False

        metadata_path = chapter_dir / "metadata.json"
        metadata = self._load_json(metadata_path)
        if metadata.get("audio_file"):
            metadata["audio_file"] = None
            self._write_json(metadata_path, metadata)

        self.io.print(f"✅ 已刪除音頻：{slug}", color="green")
        return True

    def delete_subtitle(self, chapter_dir: Path, slug: str) -> bool:
        subtitle_file = chapter_dir / "subtitles.srt"
        aligned_json = chapter_dir / "aligned_transcript.json"
        removed = False
        for target in (subtitle_file, aligned_json):
            if target.exists():
                target.unlink()
                removed = True
        if not removed:
            self.io.print(f"❌ 找不到字幕：{chapter_dir}", color="red")
            return False

        metadata_path = chapter_dir / "metadata.json"
        metadata = self._load_json(metadata_path)
        keys_to_remove = [key for key in list(metadata.keys()) if key.startswith("alignment_")]
        changed = False
        for key in keys_to_remove:
            metadata.pop(key, None)
            changed = True
        if changed:
            self._write_json(metadata_path, metadata)

        audio_meta_path = chapter_dir / "audio_metadata.json"
        audio_metadata = self._load_json(audio_meta_path)
        audio_keys = [key for key in list(audio_metadata.keys()) if key.startswith("alignment_")]
        audio_changed = False
        for key in audio_keys:
            audio_metadata.pop(key, None)
            audio_changed = True
        if audio_changed:
            self._write_json(audio_meta_path, audio_metadata)

        self.io.print(f"✅ 已刪除字幕：{slug}", color="green")
        return True

    # ------------------------------------------------------------------ Batch execution
    def run_batch(
        self,
        chapters: Sequence[str],
        batch_size: int,
        delay: int,
        label: str,
        worker: BatchWorker,
    ) -> None:
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed

        total = len(chapters)
        total_batches = (total + batch_size - 1) // batch_size
        self.io.print()
        self.io.print(f"共 {total} 章節，{label}批次大小 {batch_size}，共 {total_batches} 批。", color="white")
        start = 0
        batch_index = 1
        failures: List[str] = []
        while start < total:
            chunk = chapters[start : start + batch_size]
            self.io.print()
            self.io.print(f"{label}批次 {batch_index}/{total_batches}", color="cyan")
            for slug in chunk:
                self.io.print(f"  {slug}", color="white")
            self.io.print()
            self.io.print(f"🚀 並行執行 {len(chunk)} 個任務...", color="gray")
            with ThreadPoolExecutor(max_workers=len(chunk)) as executor:
                future_map = {executor.submit(worker, slug): slug for slug in chunk}
                for future in as_completed(future_map):
                    slug = future_map[future]
                    try:
                        future.result()
                    except subprocess.CalledProcessError:
                        failures.append(slug)
                        self.io.print(f"❌ 任務失敗：{slug}", color="red")
                    except Exception as exc:  # pragma: no cover - unexpected path
                        failures.append(slug)
                        self.io.print(f"❌ 任務失敗：{slug} ({exc})", color="red")
            start += len(chunk)
            batch_index += 1
            if start < total and delay > 0:
                self.io.print()
                self.io.print(f"⏳ 等待 {delay} 秒後處理下一批{label}...", color="gray")
                time.sleep(delay)
        if failures:
            self.io.print()
            self.io.print(f"⚠️ 部分 {label} 批次失敗：{', '.join(failures)}", color="yellow")
        else:
            self.io.print()
            self.io.print(f"✅ 全部 {label} 任務完成", color="green")

    # ------------------------------------------------------------------ JSON helpers
    def _load_json(self, path: Path) -> dict:
        if not path.exists():
            return {}
        import json

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.io.print(f"⚠️ 解析 JSON 失敗：{path}", color="yellow")
            return {}

    def _write_json(self, path: Path, payload: dict) -> None:
        import json

        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
