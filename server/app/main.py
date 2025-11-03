"""
FastAPI application that exposes storytelling output data as JSON APIs.
"""

from __future__ import annotations

import logging
from hashlib import sha256
from pathlib import Path
from typing import Generator, List, Optional, Tuple

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse

from .config import ServerSettings
from .schemas import (
    BookItem,
    ChapterItem,
    ChapterPlayback,
    TranslationRequest,
    TranslationResponse,
)
from .services import (
    BookData,
    ChapterData,
    OutputDataCache,
    SubtitleData,
    TranslationService,
    TranslationServiceError,
)
from .services.gcs_mirror import GCSMirror, is_gcs_uri

logger = logging.getLogger(__name__)


def create_app(settings: Optional[ServerSettings] = None) -> FastAPI:
    settings = settings or ServerSettings.load()
    mirror: Optional[GCSMirror] = None
    if is_gcs_uri(settings.data_root_raw):
        mirror = GCSMirror(
            settings.data_root_raw,
            settings.data_root,
        )
        try:
            mirror.sync()
        except Exception:
            logger.exception("Initial GCS sync failed")

    cache = OutputDataCache(settings.data_root, sync_hook=mirror.sync if mirror else None)
    try:
        translation_service = TranslationService.from_settings(settings)
    except TranslationServiceError as exc:
        logger.warning("Translation service disabled: %s", exc)
        translation_service = None

    app = FastAPI(
        title="Storytelling Output API",
        version="0.1.0",
        description="REST API that surfaces generated podcast books, chapters, audio, and subtitles.",
    )

    app.state.settings = settings
    app.state.cache = cache
    app.state.translation_service = translation_service
    app.state.gcs_mirror = mirror

    if settings.cors_origins:
        logger.info("Configuring CORS for origins: %s", settings.cors_origins)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(GZipMiddleware, minimum_size=settings.gzip_min_size)

    _register_routes(app)
    return app


def get_settings(request: Request) -> ServerSettings:
    return request.app.state.settings


def get_cache(request: Request) -> OutputDataCache:
    return request.app.state.cache

def get_translation_service(request: Request) -> Optional[TranslationService]:
    return getattr(request.app.state, "translation_service", None)


def _register_routes(app: FastAPI) -> None:
    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/books", response_model=List[BookItem])
    async def list_books(
        cache: OutputDataCache = Depends(get_cache),
    ) -> List[BookItem]:
        books = cache.get_books()
        return [_to_book_item(book) for book in books.values()]

    @app.get("/books/{book_id}", response_model=BookItem)
    async def get_book(
        book_id: str,
        response: Response,
        cache: OutputDataCache = Depends(get_cache),
    ) -> BookItem:
        book = cache.get_book(book_id)
        if not book:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

        etag = _build_book_etag(book)
        if etag:
            response.headers["ETag"] = etag
        return _to_book_item(book)

    @app.get("/books/{book_id}/chapters", response_model=List[ChapterItem])
    async def list_chapters(
        book_id: str,
        cache: OutputDataCache = Depends(get_cache),
    ) -> List[ChapterItem]:
        book = cache.get_book(book_id)
        if not book:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
        return [_to_chapter_item(chapter) for chapter in book.chapters.values()]

    @app.get("/books/{book_id}/chapters/{chapter_id}", response_model=ChapterPlayback)
    async def get_chapter(
        book_id: str,
        chapter_id: str,
        request: Request,
        response: Response,
        cache: OutputDataCache = Depends(get_cache),
    ) -> ChapterPlayback:
        chapter = cache.get_chapter(book_id, chapter_id)
        if not chapter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

        etag = _build_chapter_etag(chapter)
        if etag:
            response.headers["ETag"] = etag

        return _to_chapter_playback(request, book_id, chapter)

    @app.get("/books/{book_id}/chapters/{chapter_id}/audio")
    async def stream_audio(
        book_id: str,
        chapter_id: str,
        request: Request,
        cache: OutputDataCache = Depends(get_cache),
    ) -> StreamingResponse:
        chapter = cache.get_chapter(book_id, chapter_id)
        if not chapter or not chapter.audio_file:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not available")

        path = chapter.audio_file
        try:
            stat = path.stat()
        except FileNotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file missing") from None

        file_size = stat.st_size
        etag = _build_file_etag(path)
        range_header = request.headers.get("range")

        if range_header:
            start, end = _parse_range_header(range_header, file_size)
            if start is None or end is None:
                raise HTTPException(status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE)
            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "ETag": etag or "",
                "Content-Length": str(end - start + 1),
            }
            return StreamingResponse(
                _iter_file(path, start, end),
                status_code=status.HTTP_206_PARTIAL_CONTENT,
                media_type=chapter.audio_mime_type or "application/octet-stream",
                headers=headers,
            )

        headers = {
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        }
        if etag:
            headers["ETag"] = etag

        return StreamingResponse(
            _iter_file(path, 0, file_size - 1),
            media_type=chapter.audio_mime_type or "application/octet-stream",
            headers=headers,
        )

    @app.get("/books/{book_id}/chapters/{chapter_id}/subtitles", response_class=PlainTextResponse)
    async def get_subtitles(
        book_id: str,
        chapter_id: str,
        cache: OutputDataCache = Depends(get_cache),
    ):
        chapter = cache.get_chapter(book_id, chapter_id)
        if not chapter or not chapter.subtitles:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtitles not available")

        subtitles = chapter.subtitles
        if not subtitles.srt_path or not subtitles.srt_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SRT source missing")

        etag = _build_subtitle_etag(subtitles)
        headers: dict[str, str] = {
            "Content-Disposition": f'inline; filename="{book_id}_{chapter_id}.srt"',
        }
        if etag:
            headers["ETag"] = etag

        content = subtitles.srt_path.read_text(encoding="utf-8")
        return PlainTextResponse(content, media_type="text/plain; charset=utf-8", headers=headers)

    @app.post("/translations", response_model=TranslationResponse)
    async def translate_text(
        payload: TranslationRequest,
        translation_service: Optional[TranslationService] = Depends(get_translation_service),
        settings: ServerSettings = Depends(get_settings),
    ) -> TranslationResponse:
        if not translation_service:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Translation service unavailable")

        target_language = payload.target_language or settings.translation_default_target_language

        try:
            result = await run_in_threadpool(
                translation_service.translate,
                payload.text,
                target_language,
                payload.source_language,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except TranslationServiceError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        return TranslationResponse(
            translated_text=result.translated_text,
            detected_source_language=result.detected_source_language,
            cached=result.cached,
        )



def _to_book_item(book: BookData) -> BookItem:
    title = str(book.metadata.get("book_name") or book.id)
    return BookItem(id=book.id, title=title)


def _to_chapter_item(chapter: ChapterData) -> ChapterItem:
    return ChapterItem(
        id=chapter.id,
        title=chapter.title,
        chapter_number=chapter.number,
        audio_available=chapter.audio_file is not None,
        subtitles_available=chapter.subtitles is not None and chapter.subtitles.srt_path is not None,
        word_count=chapter.word_count,
        audio_duration_sec=chapter.audio_duration_sec,
        words_per_minute=chapter.words_per_minute,
    )


def _to_chapter_playback(request: Request, book_id: str, chapter: ChapterData) -> ChapterPlayback:
    audio_url: Optional[str] = None
    if chapter.audio_file:
        audio_url = str(request.url_for("stream_audio", book_id=book_id, chapter_id=chapter.id))

    subtitles_url: Optional[str] = None
    if chapter.subtitles and chapter.subtitles.srt_path:
        subtitles_url = str(request.url_for("get_subtitles", book_id=book_id, chapter_id=chapter.id))

    return ChapterPlayback(
        id=chapter.id,
        title=chapter.title,
        chapter_number=chapter.number,
        audio_url=audio_url,
        subtitles_url=subtitles_url,
        word_count=chapter.word_count,
        audio_duration_sec=chapter.audio_duration_sec,
        words_per_minute=chapter.words_per_minute,
    )


def _iter_file(path: Path, start: int, end: int, chunk_size: int = 8192) -> Generator[bytes, None, None]:
    with path.open("rb") as handle:
        handle.seek(start)
        bytes_remaining = end - start + 1
        while bytes_remaining > 0:
            read_size = min(chunk_size, bytes_remaining)
            chunk = handle.read(read_size)
            if not chunk:
                break
            yield chunk
            bytes_remaining -= len(chunk)


def _parse_range_header(range_header: str, file_size: int) -> Tuple[Optional[int], Optional[int]]:
    try:
        units, _, ranges = range_header.partition("=")
        if units.strip().lower() != "bytes":
            return None, None
        start_str, _, end_str = ranges.partition("-")
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
        if start > end or end >= file_size:
            return None, None
        return start, end
    except Exception:
        logger.exception("Invalid Range header received: %s", range_header)
        return None, None


def _build_book_etag(book: BookData) -> Optional[str]:
    components = [_file_signature(book.root / "book_metadata.json")]
    for chapter in book.chapters.values():
        components.append(_file_signature(chapter.path / "metadata.json"))
        if chapter.audio_file:
            components.append(_file_signature(chapter.audio_file))
        if chapter.subtitles and chapter.subtitles.srt_path:
            components.append(_file_signature(chapter.subtitles.srt_path))
    components = [c for c in components if c]
    if not components:
        return None
    digest = sha256("|".join(components).encode("utf-8")).hexdigest()[:16]
    return f'W/"{digest}"'


def _build_chapter_etag(chapter: ChapterData) -> Optional[str]:
    parts = [_file_signature(chapter.path / "metadata.json")]
    if chapter.audio_file:
        parts.append(_file_signature(chapter.audio_file))
    if chapter.subtitles and chapter.subtitles.srt_path:
        parts.append(_file_signature(chapter.subtitles.srt_path))
    parts = [p for p in parts if p]
    if not parts:
        return None
    digest = sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f'W/"{digest}"'


def _build_subtitle_etag(subtitles: SubtitleData) -> Optional[str]:
    if not subtitles.srt_path:
        return None
    signature = _file_signature(subtitles.srt_path)
    if not signature:
        return None
    digest = sha256(signature.encode("utf-8")).hexdigest()[:16]
    return f'W/"{digest}"'


def _build_file_etag(path: Path) -> Optional[str]:
    signature = _file_signature(path)
    if not signature:
        return None
    return f'W/"{signature}"'


def _file_signature(path: Path) -> Optional[str]:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return f"{stat.st_mtime_ns}-{stat.st_size}"


app = create_app()
