"""Task orchestration utilities that bridge FastAPI with Celery."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from celery.result import AsyncResult

from ..config import ServerSettings
from ..schemas import TaskCreate, TaskDetail, TaskItem, TaskStatus, TaskType
from ..taskqueue import celery_app, configure_celery
from .task_store import TaskRecord, TaskStore


def _parse_dt(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _to_status(state: str) -> TaskStatus:
    state = state.upper() if state else "PENDING"
    if state in {"PENDING", "RECEIVED", "QUEUED"}:
        return TaskStatus.pending
    if state in {"STARTED", "RETRY"}:
        return TaskStatus.running
    if state == "SUCCESS":
        return TaskStatus.succeeded
    return TaskStatus.failed


class TaskManager:
    """Submits jobs to Celery and exposes their status to the API layer."""

    TASK_NAME = "storytelling_cli.execute_job"

    def __init__(self, settings: ServerSettings):
        self.settings = settings
        self.store = TaskStore(settings.task_store_root)
        self.log_root = Path(settings.task_log_root)
        self.log_root.mkdir(parents=True, exist_ok=True)
        configure_celery(
            broker_url=settings.celery_broker_url,
            result_backend=settings.celery_result_backend,
        )

    def submit(self, request: TaskCreate) -> TaskDetail:
        self._validate_request(request)
        task_id = uuid.uuid4().hex
        log_path = self.log_root / f"{task_id}.log"

        options = self._build_options(request)
        options_serializable = self._ensure_jsonable(options)

        signature_kwargs = {
            "task_type": request.task_type.value,
            "chapters": list(request.chapters or []),
            "options": options_serializable,
            "log_path": str(log_path),
        }
        celery_app.signature(self.TASK_NAME).apply_async(
            kwargs=signature_kwargs,
            task_id=task_id,
        )

        record = TaskRecord(
            id=task_id,
            task_type=request.task_type.value,
            book_id=request.book_id,
            chapters=list(request.chapters or []),
            options=options_serializable,
            log_path=str(log_path),
        )
        self.store.save(record)

        return self._build_detail(record)

    def get(self, task_id: str) -> TaskDetail:
        record = self.store.load(task_id)
        if not record:
            raise KeyError(task_id)
        return self._build_detail(record)

    def list(self, limit: Optional[int] = None) -> List[TaskItem]:
        items: List[TaskItem] = []
        for record in self.store.list():
            detail = self._build_detail(record)
            items.append(TaskItem(**detail.dict(exclude={"result", "error"})))
            if limit is not None and len(items) >= limit:
                break
        return items

    def log_path(self, task_id: str) -> Path:
        record = self.store.load(task_id)
        if not record or not record.log_path:
            raise KeyError(task_id)
        path = Path(record.log_path)
        if not path.is_file():
            raise FileNotFoundError(str(path))
        resolved = path.resolve()
        root_resolved = self.log_root.resolve()
        try:
            resolved.relative_to(root_resolved)
        except ValueError:
            raise PermissionError("Log path escapes configured task log root")
        return resolved

    # Internal helpers -------------------------------------------------

    def _validate_request(self, request: TaskCreate) -> None:
        if request.task_type in (TaskType.generate_audio, TaskType.generate_subtitles):
            if not request.book_id:
                raise ValueError("book_id is required for audio or subtitle tasks")
            if not request.chapters:
                raise ValueError("chapters must be provided for audio or subtitle tasks")

    def _build_options(self, request: TaskCreate) -> Dict[str, Any]:
        options: Dict[str, Any] = {}
        if request.config_path:
            options["config_path"] = request.config_path
        elif request.task_type == TaskType.generate_script:
            options["config_path"] = str(self.settings.project_root / "podcast_config.yaml")

        if request.book_id:
            options["book_id"] = request.book_id

        if request.task_type in (TaskType.generate_audio, TaskType.generate_subtitles):
            options["output_root"] = str(self.settings.data_root)

        if request.task_type == TaskType.generate_subtitles:
            if request.subtitle_device:
                options["subtitle_device"] = request.subtitle_device
            if request.subtitle_language:
                options["subtitle_language"] = request.subtitle_language
            if request.max_words:
                options["max_words"] = request.max_words
            if request.force:
                options["force"] = request.force

        if request.env_overrides:
            options["env_overrides"] = request.env_overrides

        return options

    def _ensure_jsonable(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        serializable: Dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, Path):
                serializable[key] = str(value)
            elif isinstance(value, (list, tuple)):
                serializable[key] = [str(v) if isinstance(v, Path) else v for v in value]
            else:
                serializable[key] = value
        return serializable

    def _build_detail(self, record: TaskRecord) -> TaskDetail:
        async_result = AsyncResult(record.id, app=celery_app)
        status = _to_status(async_result.state)
        created_at = _parse_dt(record.created_at)
        updated_at = _parse_dt(record.updated_at)
        if async_result.date_done:
            date_done = async_result.date_done
            if date_done.tzinfo is None:
                date_done = date_done.replace(tzinfo=timezone.utc)
            updated_at = date_done

        result_payload: Optional[Dict[str, Any]] = None
        error_payload: Optional[str] = None
        if status == TaskStatus.succeeded:
            result = async_result.result
            if isinstance(result, dict):
                result_payload = result
        elif status == TaskStatus.failed:
            error_payload = async_result.traceback or str(async_result.result)

        return TaskDetail(
            id=record.id,
            task_type=TaskType(record.task_type),
            status=status,
            book_id=record.book_id,
            chapters=list(record.chapters),
            created_at=created_at,
            updated_at=updated_at,
            log_path=record.log_path,
            result=result_payload,
            error=error_payload,
        )
