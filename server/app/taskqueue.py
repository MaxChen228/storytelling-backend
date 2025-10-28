"""Celery integration for long-running podcast tasks."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from celery import Celery

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "generate_script.py"
AUDIO_PATH = PROJECT_ROOT / "generate_audio.py"
SUBTITLE_PATH = PROJECT_ROOT / "generate_subtitles.py"

celery_app = Celery("storytelling_cli")


def configure_celery(*, broker_url: str, result_backend: str) -> Celery:
    """Configure the global Celery app."""
    celery_app.conf.update(
        broker_url=broker_url,
        result_backend=result_backend,
        task_track_started=True,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_time_limit=60 * 60,  # 1 hour
        task_soft_time_limit=55 * 60,
    )
    return celery_app


def _utcnow() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _run_command(command: List[str], log_handle, *, env: Optional[Dict[str, str]] = None) -> None:
    log_handle.write(f"[{_utcnow()}] $ {' '.join(command)}\n")
    log_handle.flush()
    process = subprocess.Popen(
        command,
        stdout=log_handle,
        stderr=log_handle,
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    returncode = process.wait()
    if returncode != 0:
        raise RuntimeError(f"Command failed with exit code {returncode}: {' '.join(command)}")


def _ensure_env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    env = os.environ.copy()
    if extra:
        env.update({k: str(v) for k, v in extra.items()})
    return env


def _job_generate_scripts(
    chapters: Iterable[str],
    *,
    config_path: Optional[str],
    env_overrides: Optional[Dict[str, str]],
    log_handle,
) -> Dict[str, Any]:
    env = _ensure_env(env_overrides)
    processed: List[str] = []
    chapter_list = list(chapters)
    if not chapter_list:
        command = [sys.executable, str(SCRIPT_PATH)]
        if config_path:
            command.extend(["--config", config_path])
        _run_command(command, log_handle, env=env)
        return {"chapters": processed or None}

    for chapter in chapter_list:
        command = [sys.executable, str(SCRIPT_PATH)]
        if config_path:
            command.extend(["--config", config_path])
        command.append(chapter)
        _run_command(command, log_handle, env=env)
        processed.append(chapter)
    return {"chapters": processed}


def _job_generate_audio(
    chapters: Iterable[str],
    *,
    book_id: str,
    output_root: str,
    env_overrides: Optional[Dict[str, str]],
    log_handle,
) -> Dict[str, Any]:
    env = _ensure_env(env_overrides)
    output_base = Path(output_root) / book_id
    targets: List[str] = []
    for chapter in chapters:
        chapter_dir = output_base / chapter
        if not chapter_dir.exists():
            raise FileNotFoundError(f"Chapter directory missing: {chapter_dir}")
        command = [sys.executable, str(AUDIO_PATH), str(chapter_dir)]
        _run_command(command, log_handle, env=env)
        targets.append(str(chapter_dir))
    return {"chapters": list(chapters), "targets": targets}


def _job_generate_subtitles(
    chapters: Iterable[str],
    *,
    book_id: str,
    output_root: str,
    env_overrides: Optional[Dict[str, str]],
    subtitle_device: Optional[str],
    subtitle_language: Optional[str],
    force: bool,
    max_words: Optional[int],
    log_handle,
) -> Dict[str, Any]:
    env = _ensure_env(env_overrides)
    output_base = Path(output_root) / book_id
    generated: List[str] = []
    for chapter in chapters:
        chapter_dir = output_base / chapter
        if not chapter_dir.exists():
            raise FileNotFoundError(f"Chapter directory missing: {chapter_dir}")
        command = [sys.executable, str(SUBTITLE_PATH), str(chapter_dir)]
        if subtitle_device:
            command.extend(["--device", subtitle_device])
        if subtitle_language:
            command.extend(["--language", subtitle_language])
        if force:
            command.append("--force")
        if max_words:
            command.extend(["--max-words", str(max_words)])
        _run_command(command, log_handle, env=env)
        generated.append(str(chapter_dir))
    return {"chapters": list(chapters), "targets": generated}


@celery_app.task(name="storytelling_cli.execute_job", bind=True)
def execute_job(
    self,
    *,
    task_type: str,
    chapters: Optional[List[str]] = None,
    options: Optional[Dict[str, Any]] = None,
    log_path: str,
) -> Dict[str, Any]:
    options = options or {}
    chapters = chapters or []
    log_file = Path(log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"[{_utcnow()}] Task {task_type} started\n")
        handle.flush()
        if task_type == "generate_script":
            result_payload = _job_generate_scripts(
                chapters,
                config_path=options.get("config_path"),
                env_overrides=options.get("env_overrides"),
                log_handle=handle,
            )
        elif task_type == "generate_audio":
            book_id = options.get("book_id")
            output_root = options.get("output_root")
            if not book_id or not output_root:
                raise ValueError("book_id and output_root are required for audio generation tasks")
            result_payload = _job_generate_audio(
                chapters,
                book_id=book_id,
                output_root=output_root,
                env_overrides=options.get("env_overrides"),
                log_handle=handle,
            )
        elif task_type == "generate_subtitles":
            book_id = options.get("book_id")
            output_root = options.get("output_root")
            if not book_id or not output_root:
                raise ValueError("book_id and output_root are required for subtitle generation tasks")
            result_payload = _job_generate_subtitles(
                chapters,
                book_id=book_id,
                output_root=output_root,
                env_overrides=options.get("env_overrides"),
                subtitle_device=options.get("subtitle_device"),
                subtitle_language=options.get("subtitle_language"),
                force=bool(options.get("force", False)),
                max_words=options.get("max_words"),
                log_handle=handle,
            )
        else:
            raise ValueError(f"Unsupported task_type: {task_type}")

        handle.write(f"[{_utcnow()}] Task {task_type} finished\n")
        handle.flush()
    result_payload.setdefault("log_path", str(log_file))
    return result_payload
