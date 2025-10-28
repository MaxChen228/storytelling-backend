"""Google Cloud Translation service wrapper with simple LRU cache."""

from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING, Tuple

if TYPE_CHECKING:  # pragma: no cover - only for type checking
    from ..config import ServerSettings

logger = logging.getLogger(__name__)


class TranslationServiceError(RuntimeError):
    """Raised when the translation service cannot fulfill a request."""


@dataclass(frozen=True)
class TranslationResult:
    translated_text: str
    detected_source_language: Optional[str] = None
    cached: bool = False


class TranslationService:
    """Thin wrapper around Google Cloud Translation with LRU caching."""

    def __init__(
        self,
        client,
        parent: str,
        default_target_language: str = "zh-TW",
        max_cache_entries: int = 256,
    ) -> None:
        self._client = client
        self._parent = parent
        self._default_target_language = default_target_language
        self._max_cache_entries = max(1, max_cache_entries)
        self._cache: "OrderedDict[Tuple[str, str, str], Tuple[str, Optional[str]]]" = OrderedDict()

    @classmethod
    def from_settings(cls, settings: "ServerSettings") -> Optional["TranslationService"]:
        project_id = settings.google_translate_project_id
        if not project_id:
            logger.info("Google Translate project ID not configured; translation disabled.")
            return None

        try:
            from google.cloud import translate  # type: ignore import
        except ImportError as exc:  # pragma: no cover - only triggered when dependency missing
            logger.warning("google-cloud-translate package is not installed: %s", exc)
            return None

        location = settings.google_translate_location or "global"
        parent = f"projects/{project_id}/locations/{location}"

        try:
            client = translate.TranslationServiceClient()
        except Exception as exc:  # pragma: no cover - requires misconfigured credentials
            logger.exception("Failed to initialize TranslationServiceClient")
            raise TranslationServiceError("Failed to initialize Google Translation client") from exc

        cache_size = max(1, settings.translation_cache_size)
        default_target = settings.translation_default_target_language or "zh-TW"

        return cls(
            client=client,
            parent=parent,
            default_target_language=default_target,
            max_cache_entries=cache_size,
        )

    def translate(
        self,
        text: str,
        target_language: Optional[str] = None,
        source_language: Optional[str] = None,
    ) -> TranslationResult:
        normalized_text = (text or "").strip()
        if not normalized_text:
            raise ValueError("Text must not be empty.")

        target = (target_language or self._default_target_language or "").strip()
        if not target:
            raise TranslationServiceError("Target language is not configured.")

        source = (source_language or "").strip()
        cache_key = (normalized_text, target.lower(), source.lower())

        cached_value = self._cache.get(cache_key)
        if cached_value:
            translated_text, detected_language = cached_value
            self._cache.move_to_end(cache_key)
            return TranslationResult(
                translated_text=translated_text,
                detected_source_language=detected_language,
                cached=True,
            )

        request = {
            "parent": self._parent,
            "contents": [normalized_text],
            "target_language_code": target,
            "mime_type": "text/plain",
        }
        if source:
            request["source_language_code"] = source

        try:
            response = self._client.translate_text(request=request)
        except Exception as exc:  # pragma: no cover - network/service level failure
            logger.exception("Translation request failed")
            raise TranslationServiceError("Translation request failed") from exc

        translations = getattr(response, "translations", None)
        if not translations:
            raise TranslationServiceError("Translation service returned no results.")

        translation = translations[0]
        translated_text = getattr(translation, "translated_text", None)
        if not translated_text:
            raise TranslationServiceError("Translation response missing translated text.")

        detected_language = getattr(translation, "detected_language_code", None) or (source or None)

        self._cache[cache_key] = (translated_text, detected_language)
        self._prune_cache()

        return TranslationResult(
            translated_text=translated_text,
            detected_source_language=detected_language,
            cached=False,
        )

    def _prune_cache(self) -> None:
        while len(self._cache) > self._max_cache_entries:
            self._cache.popitem(last=False)
