"""Persistent bookkeeping for task submissions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Iterable, List, Optional


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@dataclass
class TaskRecord:
    """Metadata recorded when a task is submitted."""

    id: str
    task_type: str
    book_id: Optional[str]
    chapters: List[str] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utcnow_iso)
    updated_at: str = field(default_factory=_utcnow_iso)
    log_path: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "TaskRecord":
        return cls(
            id=payload["id"],
            task_type=payload["task_type"],
            book_id=payload.get("book_id"),
            chapters=list(payload.get("chapters", [])),
            options=dict(payload.get("options", {})),
            created_at=payload.get("created_at") or _utcnow_iso(),
            updated_at=payload.get("updated_at") or _utcnow_iso(),
            log_path=payload.get("log_path"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TaskStore:
    """Simple filesystem-based registry of submitted tasks."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def record_path(self, task_id: str) -> Path:
        return self.root / f"{task_id}.json"

    def save(self, record: TaskRecord) -> None:
        with self._lock:
            record.updated_at = _utcnow_iso()
            _atomic_write_json(self.record_path(record.id), record.to_dict())

    def load(self, task_id: str) -> Optional[TaskRecord]:
        payload = _load_json(self.record_path(task_id))
        if payload is None:
            return None
        return TaskRecord.from_dict(payload)

    def exists(self, task_id: str) -> bool:
        return self.record_path(task_id).exists()

    def list(self) -> Iterable[TaskRecord]:
        records: List[TaskRecord] = []
        for path in sorted(self.root.glob("*.json")):
            payload = _load_json(path)
            if not isinstance(payload, dict):
                continue
            try:
                records.append(TaskRecord.from_dict(payload))
            except KeyError:
                continue
        records.sort(key=lambda record: record.created_at, reverse=True)
        return records
