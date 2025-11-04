"""Sentence explanation service powered by Gemini."""

from __future__ import annotations

import json
import logging
import os
from collections import OrderedDict
from dataclasses import dataclass, replace
from hashlib import sha256
from textwrap import dedent
from typing import List, Optional, Tuple, TYPE_CHECKING

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from ...config import ServerSettings


class SentenceExplanationError(RuntimeError):
    """Raised when the Gemini explainer cannot fulfill a request."""


@dataclass(frozen=True)
class VocabularyEntry:
    word: str
    meaning: str
    note: Optional[str] = None


@dataclass(frozen=True)
class SentenceExplanationResult:
    overview: str
    key_points: Tuple[str, ...]
    vocabulary: Tuple[VocabularyEntry, ...]
    cached: bool = False


class SentenceExplanationService:
    """Generates sentence-level explanations using Gemini."""

    def __init__(
        self,
        client,
        types_module,
        model: str,
        timeout: float = 30.0,
        max_cache_entries: int = 128,
    ) -> None:
        self._client = client
        self._types = types_module
        self._model = model
        self._timeout = max(1.0, float(timeout))
        self._max_cache_entries = max(1, int(max_cache_entries))
        self._cache: "OrderedDict[str, SentenceExplanationResult]" = OrderedDict()

    @classmethod
    def from_settings(cls, settings: "ServerSettings") -> Optional["SentenceExplanationService"]:
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.info("GEMINI_API_KEY is not configured; sentence explanation disabled.")
            return None

        try:
            from google import genai  # type: ignore import
            from google.genai import types  # type: ignore import
        except ImportError as exc:  # pragma: no cover - dependency missing
            logger.warning("google-genai package is not installed: %s", exc)
            return None

        model = settings.sentence_explainer_model or "gemini-2.5-flash-lite"
        timeout = settings.sentence_explainer_timeout or 30.0
        cache_size = settings.sentence_explainer_cache_size or 128

        try:
            client = genai.Client(api_key=api_key)
        except Exception as exc:  # pragma: no cover - credential misconfiguration
            logger.exception("Failed to initialize Gemini client")
            raise SentenceExplanationError("Failed to initialize Gemini client") from exc

        return cls(
            client=client,
            types_module=types,
            model=model,
            timeout=timeout,
            max_cache_entries=cache_size,
        )

    def explain_sentence(
        self,
        sentence: str,
        previous_sentence: str = "",
        next_sentence: str = "",
        language: str = "zh-TW",
    ) -> SentenceExplanationResult:
        normalized_sentence = (sentence or "").strip()
        if not normalized_sentence:
            raise ValueError("Sentence must not be empty.")

        language = (language or "zh-TW").strip() or "zh-TW"
        previous_sentence = (previous_sentence or "").strip()
        next_sentence = (next_sentence or "").strip()

        cache_key_payload = json.dumps(
            {
                "model": self._model,
                "sentence": normalized_sentence,
                "previous": previous_sentence,
                "next": next_sentence,
                "language": language,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        cache_key = sha256(cache_key_payload.encode("utf-8")).hexdigest()

        cached_result = self._cache.get(cache_key)
        if cached_result:
            self._cache.move_to_end(cache_key)
            return replace(cached_result, cached=True)

        prompt = self._build_prompt(
            sentence=normalized_sentence,
            previous_sentence=previous_sentence,
            next_sentence=next_sentence,
            language=language,
        )

        generate_config = self._types.GenerateContentConfig(
            temperature=0.3,
            response_mime_type="application/json",
        )

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=generate_config,
            )
        except Exception as exc:  # pragma: no cover - network/service failure
            logger.exception("Gemini sentence explanation request failed")
            raise SentenceExplanationError("Sentence explanation request failed") from exc

        raw_text = self._extract_text(response)
        if not raw_text:
            raise SentenceExplanationError("Explanation service returned an empty response.")

        data = self._parse_json(raw_text)

        overview = self._ensure_string(data.get("overview", ""), fallback="(無法取得概述)")
        key_points = tuple(self._normalize_list(data.get("key_points", [])))
        vocabulary_entries = tuple(self._parse_vocabulary(data.get("vocabulary", [])))

        result = SentenceExplanationResult(
            overview=overview,
            key_points=key_points,
            vocabulary=vocabulary_entries,
            cached=False,
        )

        self._cache[cache_key] = result
        self._prune_cache()

        return result

    def explain_phrase(
        self,
        phrase: str,
        sentence: str,
        previous_sentence: str = "",
        next_sentence: str = "",
        language: str = "zh-TW",
    ) -> SentenceExplanationResult:
        """
        解釋詞組在句子中的用法。

        Args:
            phrase: 用戶選中的詞組
            sentence: 完整句子
            previous_sentence: 前一句(提供上下文)
            next_sentence: 後一句(提供上下文)
            language: 目標語言

        Returns:
            SentenceExplanationResult: 詞組解釋結果

        Raises:
            ValueError: 當 phrase 或 sentence 為空時
            SentenceExplanationError: 當 LLM 調用失敗時
        """
        # 驗證輸入
        raw_phrase = (phrase or "").strip()
        if not raw_phrase:
            raise ValueError("Phrase must not be empty.")

        normalized_sentence = (sentence or "").strip()
        if not normalized_sentence:
            raise ValueError("Sentence must not be empty.")

        # 正規化詞組以提高快取命中率
        normalized_phrase = self._normalize_phrase(raw_phrase)
        if not normalized_phrase:
            raise ValueError("Phrase must not be empty after normalization.")

        language = (language or "zh-TW").strip() or "zh-TW"
        previous_sentence = (previous_sentence or "").strip()
        next_sentence = (next_sentence or "").strip()

        # 建立快取鍵(加上 "phrase:" 前綴以區分句子解釋)
        cache_key_payload = json.dumps(
            {
                "type": "phrase",
                "model": self._model,
                "phrase": normalized_phrase,
                "sentence": normalized_sentence,
                "previous": previous_sentence,
                "next": next_sentence,
                "language": language,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        cache_key = sha256(cache_key_payload.encode("utf-8")).hexdigest()

        # 檢查快取
        cached_result = self._cache.get(cache_key)
        if cached_result:
            self._cache.move_to_end(cache_key)
            return replace(cached_result, cached=True)

        # 建立詞組解釋的 prompt
        prompt = self._build_phrase_prompt(
            phrase=raw_phrase,  # 使用原始 phrase 傳給 LLM(包含大小寫和標點)
            sentence=normalized_sentence,
            previous_sentence=previous_sentence,
            next_sentence=next_sentence,
            language=language,
        )

        # 調用 LLM
        generate_config = self._types.GenerateContentConfig(
            temperature=0.3,
            response_mime_type="application/json",
        )

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=generate_config,
            )
        except Exception as exc:  # pragma: no cover - network/service failure
            logger.exception("Gemini phrase explanation request failed")
            raise SentenceExplanationError("Phrase explanation request failed") from exc

        # 解析回應(復用現有的解析邏輯)
        raw_text = self._extract_text(response)
        if not raw_text:
            raise SentenceExplanationError("Explanation service returned an empty response.")

        data = self._parse_json(raw_text)

        overview = self._ensure_string(data.get("overview", ""), fallback="(無法取得概述)")
        key_points = tuple(self._normalize_list(data.get("key_points", [])))
        vocabulary_entries = tuple(self._parse_vocabulary(data.get("vocabulary", [])))

        result = SentenceExplanationResult(
            overview=overview,
            key_points=key_points,
            vocabulary=vocabulary_entries,
            cached=False,
        )

        # 更新快取
        self._cache[cache_key] = result
        self._prune_cache()

        return result

    def _extract_text(self, response) -> str:
        text = getattr(response, "text", None)
        if text:
            return text.strip()

        candidates = getattr(response, "candidates", []) or []
        parts: List[str] = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", []) or []:
                part_text = getattr(part, "text", None)
                if part_text:
                    parts.append(str(part_text))
        return "\n".join(parts).strip()

    def _parse_json(self, raw_text: str) -> dict:
        text = raw_text.strip()
        if "```" in text:
            start = text.find("```json")
            if start != -1:
                start = text.find("\n", start) + 1
                end = text.find("```", start)
                if end != -1:
                    text = text[start:end].strip()
            else:
                start = text.find("```")
                end = text.rfind("```")
                if start != -1 and end != -1 and end > start:
                    text = text[start + 3 : end].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.debug("Failed to parse JSON from response: %s", text)
            raise SentenceExplanationError("Explanation service returned invalid JSON.") from exc

    def _normalize_list(self, value) -> List[str]:
        if isinstance(value, list):
            return [self._ensure_string(item, "").strip() for item in value if self._ensure_string(item, "").strip()]
        if isinstance(value, str):
            stripped = value.strip()
            return [stripped] if stripped else []
        return []

    def _ensure_string(self, value, fallback: str) -> str:
        if isinstance(value, str):
            return value.strip() or fallback
        if value is None:
            return fallback
        return str(value).strip() or fallback

    def _parse_vocabulary(self, items) -> List[VocabularyEntry]:
        entries: List[VocabularyEntry] = []
        if not isinstance(items, list):
            return entries

        for item in items:
            if not isinstance(item, dict):
                continue
            word = self._ensure_string(item.get("word"), "")
            meaning = self._ensure_string(item.get("meaning"), "")
            note_value = item.get("note")
            note = self._ensure_string(note_value, "") if note_value is not None else None
            if not word or not meaning:
                continue
            entries.append(VocabularyEntry(word=word, meaning=meaning, note=note))
        return entries

    def _prune_cache(self) -> None:
        while len(self._cache) > self._max_cache_entries:
            self._cache.popitem(last=False)

    def _normalize_phrase(self, phrase: str) -> str:
        """
        正規化詞組以提高快取命中率。

        處理流程:
        1. 統一小寫
        2. 移除前後標點符號 (保留內部縮寫如 I'm, don't)
        3. 壓縮多餘空格
        """
        normalized = phrase.lower().strip()
        # 移除前後常見標點符號,但保留內部的撇號和連字號
        punctuation = ".,!?;:\"\'"
        normalized = normalized.strip(punctuation)
        # 壓縮多餘空格
        normalized = " ".join(normalized.split())
        return normalized

    def _build_prompt(
        self,
        sentence: str,
        previous_sentence: str,
        next_sentence: str,
        language: str,
    ) -> str:
        prev_context = previous_sentence or "(無前一句)"
        next_context = next_sentence or "(無後一句)"

        return dedent(
            f"""
            用{language}精簡解釋這個英語句子。避免冗長分析，直接說重點。

            [前一句] {prev_context}
            [重點句] {sentence}
            [後一句] {next_context}

            以 JSON 格式回答：
            {{
              "overview": "整句意思（1-2 句話）",
              "key_points": ["語法或用法重點，每點 10-15 字"],
              "vocabulary": [{{"word": "單字", "meaning": "中文", "note": "補充（可選）"}}]
            }}

            要求：精簡、直接、避免教學式冗述。
            """
        ).strip()

    def _build_phrase_prompt(
        self,
        phrase: str,
        sentence: str,
        previous_sentence: str,
        next_sentence: str,
        language: str,
    ) -> str:
        """建立詞組解釋的 prompt,專注於詞組用法而非整句翻譯。"""
        prev_context = previous_sentence or "(無前一句)"
        next_context = next_sentence or "(無後一句)"

        return dedent(
            f"""
            用{language}精簡解釋詞組「{phrase}」在句子中的用法。

            [句子] {sentence}
            [前一句] {prev_context}
            [後一句] {next_context}

            以 JSON 格式回答：
            {{
              "overview": "詞組意思（1 句話）",
              "key_points": ["用法重點，每點 10-15 字"],
              "vocabulary": [{{"word": "單字", "meaning": "中文", "note": "補充（可選）"}}]
            }}

            要求：精簡、直接、只講詞組用法。
            """
        ).strip()
