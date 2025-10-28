"""定義前端真正需要的精簡 Pydantic schema。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BookItem(BaseModel):
    """書籍清單項目。"""

    id: str
    title: str


class ChapterItem(BaseModel):
    """章節清單項目。"""

    id: str
    title: str
    chapter_number: Optional[int] = None
    audio_available: bool = False
    subtitles_available: bool = False


class ChapterPlayback(BaseModel):
    """播放頁面需要的章節資訊。"""

    id: str
    title: str
    chapter_number: Optional[int] = None
    audio_url: Optional[str] = None
    subtitles_url: Optional[str] = None


class TranslationRequest(BaseModel):
    """翻譯請求內容。"""

    text: str = Field(..., min_length=1, max_length=5000)
    target_language: Optional[str] = Field(default=None, alias="target_language_code")
    source_language: Optional[str] = Field(default=None, alias="source_language_code")
    book_id: Optional[str] = None
    chapter_id: Optional[str] = None
    subtitle_id: Optional[int] = None

    class Config:
        populate_by_name = True


class TranslationResponse(BaseModel):
    """翻譯結果回應。"""

    translated_text: str
    detected_source_language: Optional[str] = None
    cached: bool = False


class TaskType(str, Enum):
    generate_script = "generate_script"
    generate_audio = "generate_audio"
    generate_subtitles = "generate_subtitles"


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class TaskCreate(BaseModel):
    task_type: TaskType
    book_id: Optional[str] = None
    chapters: Optional[List[str]] = None
    config_path: Optional[str] = None
    force: bool = False
    subtitle_device: Optional[str] = None
    subtitle_language: Optional[str] = None
    max_words: Optional[int] = None
    env_overrides: Dict[str, str] = Field(default_factory=dict)


class TaskItem(BaseModel):
    id: str
    task_type: TaskType
    status: TaskStatus
    book_id: Optional[str] = None
    chapters: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    log_path: Optional[str] = None


class TaskDetail(TaskItem):
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
