"""
Configuration helpers for the FastAPI backend.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv


def _resolve_path(raw: str) -> Path:
    """Resolves a potentially relative path against the project root."""
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return candidate
    project_root = Path(__file__).resolve().parents[2]
    return (project_root / candidate).resolve()


@dataclass
class ServerSettings:
    """Settings object populated from environment variables."""

    project_root: Path = field(default_factory=lambda: _resolve_path("."))
    data_root: Path = field(default_factory=lambda: _resolve_path("output"))
    cors_origins: List[str] = field(default_factory=list)
    gzip_min_size: int = 512
    google_translate_project_id: Optional[str] = None
    google_translate_location: str = "global"
    translation_default_target_language: str = "zh-TW"
    translation_cache_size: int = 256

    @classmethod
    def load(cls) -> "ServerSettings":
        load_dotenv()

        project_root = _resolve_path(".")
        data_root = _resolve_path(os.getenv("DATA_ROOT", "output"))
        cors_raw = os.getenv("CORS_ORIGINS", "")
        cors_origins = [origin.strip() for origin in cors_raw.split(",") if origin.strip()]
        gzip_min_size = int(os.getenv("GZIP_MIN_SIZE", "512"))
        google_translate_project_id = os.getenv("GOOGLE_TRANSLATE_PROJECT_ID")
        google_translate_location = os.getenv("GOOGLE_TRANSLATE_LOCATION", "global")
        translation_default_target_language = os.getenv("TRANSLATION_DEFAULT_TARGET_LANGUAGE", "zh-TW")
        translation_cache_size = int(os.getenv("TRANSLATION_CACHE_SIZE", "256"))

        return cls(
            project_root=project_root,
            data_root=data_root,
            cors_origins=cors_origins,
            gzip_min_size=gzip_min_size,
            google_translate_project_id=google_translate_project_id,
            google_translate_location=google_translate_location,
            translation_default_target_language=translation_default_target_language,
            translation_cache_size=translation_cache_size,
        )
