"""定義前端真正需要的精簡 Pydantic schema。"""

from __future__ import annotations

from typing import Optional

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

