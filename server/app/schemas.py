"""定義前端真正需要的精簡 Pydantic schema。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class BookItem(BaseModel):
    """書籍清單項目。"""

    id: str
    title: str
    cover_url: Optional[str] = None
    model_config = ConfigDict(exclude_none=True)


class ChapterItem(BaseModel):
    """章節清單項目。"""

    id: str
    title: str
    chapter_number: Optional[int] = None
    audio_available: bool = False
    subtitles_available: bool = False
    word_count: Optional[int] = None
    audio_duration_sec: Optional[float] = None
    words_per_minute: Optional[float] = None


class ChapterPlayback(BaseModel):
    """播放頁面需要的章節資訊。"""

    id: str
    title: str
    chapter_number: Optional[int] = None
    audio_url: Optional[str] = None
    subtitles_url: Optional[str] = None
    word_count: Optional[int] = None
    audio_duration_sec: Optional[float] = None
    words_per_minute: Optional[float] = None


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


class SentenceExplanationVocabulary(BaseModel):
    """句子重點的詞彙解釋。"""

    word: str
    meaning: str
    note: Optional[str] = None


class SentenceExplanationRequest(BaseModel):
    """句子解釋請求。"""

    sentence: str = Field(..., min_length=1, max_length=2000)
    previous_sentence: Optional[str] = Field(default="", max_length=2000)
    next_sentence: Optional[str] = Field(default="", max_length=2000)
    language: Optional[str] = Field(default="zh-TW", min_length=2, max_length=16)


class PhraseExplanationRequest(BaseModel):
    """詞組解釋請求。"""

    phrase: str = Field(..., min_length=1, max_length=200, description="用戶選中的詞組")
    sentence: str = Field(..., min_length=1, max_length=2000, description="完整句子")
    previous_sentence: Optional[str] = Field(default="", max_length=2000)
    next_sentence: Optional[str] = Field(default="", max_length=2000)
    language: Optional[str] = Field(default="zh-TW", min_length=2, max_length=16)


class SentenceExplanationResponse(BaseModel):
    """句子解釋回應。"""

    overview: str
    key_points: list[str] = Field(default_factory=list)
    vocabulary: list[SentenceExplanationVocabulary] = Field(default_factory=list)
    cached: bool = False


class AssetList(BaseModel):
    """資源清單回應。"""

    assets: list[str] = Field(default_factory=list, description="Available asset filenames")
