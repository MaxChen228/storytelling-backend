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
    data_root_raw: str = "output"
    cors_origins: List[str] = field(default_factory=list)
    gzip_min_size: int = 512
    sentence_explainer_model: str = "gemini-2.5-flash-lite"
    sentence_explainer_timeout: float = 30.0
    sentence_explainer_cache_size: int = 128
    media_delivery_mode: str = "local"
    gcs_mirror_include_suffixes: Optional[List[str]] = None
    signed_url_ttl_seconds: int = 600

    @classmethod
    def load(cls) -> "ServerSettings":
        load_dotenv()

        project_root = _resolve_path(".")
        data_root_raw = os.getenv("DATA_ROOT", "output")
        if data_root_raw.startswith("gs://"):
            cache_root = os.getenv("STORYTELLING_GCS_CACHE_DIR", "/tmp/storytelling-output")
            data_root = Path(cache_root).expanduser().resolve()
        else:
            data_root = _resolve_path(data_root_raw)
        cors_raw = os.getenv("CORS_ORIGINS", "")
        cors_origins = [origin.strip() for origin in cors_raw.split(",") if origin.strip()]
        gzip_min_size = int(os.getenv("GZIP_MIN_SIZE", "512"))
        sentence_explainer_model = os.getenv("SENTENCE_EXPLAINER_MODEL", "gemini-2.5-flash-lite")
        sentence_explainer_timeout = float(os.getenv("SENTENCE_EXPLAINER_TIMEOUT", "30"))
        sentence_explainer_cache_size = int(os.getenv("SENTENCE_EXPLAINER_CACHE_SIZE", "128"))
        media_delivery_mode = (os.getenv("MEDIA_DELIVERY_MODE", "local") or "local").strip().lower()
        include_suffixes_raw = os.getenv("GCS_MIRROR_INCLUDE_SUFFIXES", "").strip()
        include_suffixes: Optional[List[str]]
        if include_suffixes_raw:
            include_suffixes = []
            for item in include_suffixes_raw.split(","):
                normalized = item.strip()
                if not normalized:
                    continue
                if not normalized.startswith("."):
                    normalized = f".{normalized}"
                include_suffixes.append(normalized.lower())
            if not include_suffixes:
                include_suffixes = None
        else:
            include_suffixes = None
        signed_url_ttl_seconds = max(60, int(os.getenv("SIGNED_URL_TTL_SECONDS", "600")))

        return cls(
            project_root=project_root,
            data_root=data_root,
            data_root_raw=data_root_raw,
            cors_origins=cors_origins,
            gzip_min_size=gzip_min_size,
            sentence_explainer_model=sentence_explainer_model,
            sentence_explainer_timeout=sentence_explainer_timeout,
            sentence_explainer_cache_size=sentence_explainer_cache_size,
            media_delivery_mode=media_delivery_mode,
            gcs_mirror_include_suffixes=include_suffixes,
            signed_url_ttl_seconds=signed_url_ttl_seconds,
        )
