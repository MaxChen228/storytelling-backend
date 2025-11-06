"""
FastAPI application that exposes storytelling output data as JSON APIs.
"""

from __future__ import annotations

import logging
from hashlib import sha256
from pathlib import Path
from typing import Generator, List, Optional, Tuple
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse

from .config import ServerSettings
from .schemas import (
    AssetList,
    BookItem,
    ChapterItem,
    ChapterPlayback,
    PhraseExplanationRequest,
    SentenceExplanationRequest,
    SentenceExplanationResponse,
    SentenceExplanationVocabulary,
    TranslationRequest,
    TranslationResponse,
)
from .services import (
    BookData,
    ChapterData,
    OutputDataCache,
    SentenceExplanationError,
    SentenceExplanationResult,
    SentenceExplanationService,
    SubtitleData,
    TranslationService,
    TranslationServiceError,
)
from .services.gcs_mirror import GCSMirror, is_gcs_uri, parse_gcs_uri
from .services.storage_signer import generate_signed_url

logger = logging.getLogger(__name__)


def _as_public_gcs_url(uri: str) -> Optional[str]:
    if not uri:
        return None
    if uri.startswith("http://") or uri.startswith("https://"):
        return uri
    if uri.startswith("gs://"):
        bucket, object_path = parse_gcs_uri(uri)
        if not object_path:
            return f"https://storage.googleapis.com/{bucket}"
        return f"https://storage.googleapis.com/{bucket}/{object_path}"
    return None


def _guess_content_type(path: Path) -> str:
    """Guess content type based on file extension."""
    suffix = path.suffix.lower()
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".pdf": "application/pdf",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".json": "application/json",
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
    }
    return content_types.get(suffix, "application/octet-stream")


def create_app(settings: Optional[ServerSettings] = None) -> FastAPI:
    settings = settings or ServerSettings.load()
    mirror: Optional[GCSMirror] = None
    download_suffixes: Optional[set[str]] = None
    cache_relevant_suffixes: Optional[set[str]] = None

    if is_gcs_uri(settings.data_root_raw):
        # 診斷日誌：檢查 GCS 配置
        import os
        logger.info("=== GCS Configuration Diagnostics ===")
        logger.info(f"DATA_ROOT: {settings.data_root_raw}")
        logger.info(f"Local cache: {settings.data_root}")
        logger.info(f"Media delivery mode: {settings.media_delivery_mode}")
        logger.info(f"GCS_MIRROR_INCLUDE_SUFFIXES: {settings.gcs_mirror_include_suffixes}")
        logger.info(f"GOOGLE_APPLICATION_CREDENTIALS: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")

        # 檢查 credentials 檔案
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_path:
            if os.path.exists(creds_path):
                logger.info(f"✅ Credentials file exists at {creds_path}")
                try:
                    import json
                    with open(creds_path, 'r') as f:
                        creds_data = json.load(f)
                    logger.info(f"✅ Credentials file is valid JSON")
                    logger.info(f"   Project ID: {creds_data.get('project_id')}")
                    logger.info(f"   Client email: {creds_data.get('client_email')}")
                except Exception as e:
                    logger.error(f"❌ Failed to parse credentials file: {e}")
            else:
                logger.error(f"❌ Credentials file NOT found at {creds_path}")
        else:
            logger.warning("⚠️ GOOGLE_APPLICATION_CREDENTIALS not set")

        logger.info("=== End Diagnostics ===")

        if settings.gcs_mirror_include_suffixes:
            download_suffixes = set(settings.gcs_mirror_include_suffixes)
        elif settings.media_delivery_mode in {"gcs-signed", "gcs-public"}:
            download_suffixes = {".json"}
        if download_suffixes:
            cache_relevant_suffixes = set(download_suffixes)

        logger.info(f"Creating GCSMirror with download_suffixes: {download_suffixes}")

        try:
            mirror = GCSMirror(
                settings.data_root_raw,
                settings.data_root,
                download_suffixes=download_suffixes,
            )
            logger.info("✅ GCSMirror instance created")
        except Exception as e:
            logger.exception(f"❌ Failed to create GCSMirror: {e}")
            raise

        try:
            logger.info("Starting GCS sync...")
            mirror.sync()
            logger.info("✅ GCS sync completed successfully")
        except Exception as e:
            logger.exception("❌ Initial GCS sync failed")
            raise

    cache = OutputDataCache(
        settings.data_root,
        sync_hook=mirror.sync if mirror else None,
        mirror=mirror,
        relevant_suffixes=cache_relevant_suffixes,
    )
    try:
        translation_service = TranslationService.from_settings(settings)
    except TranslationServiceError as exc:
        logger.warning("Translation service disabled: %s", exc)
        translation_service = None

    try:
        explanation_service = SentenceExplanationService.from_settings(settings)
    except SentenceExplanationError as exc:
        logger.warning("Sentence explanation disabled: %s", exc)
        explanation_service = None

    app = FastAPI(
        title="Storytelling Output API",
        version="0.1.0",
        description="REST API that surfaces generated podcast books, chapters, audio, and subtitles.",
    )

    app.state.settings = settings
    app.state.cache = cache
    app.state.translation_service = translation_service
    app.state.sentence_explainer = explanation_service
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


def get_sentence_explainer(request: Request) -> Optional[SentenceExplanationService]:
    return getattr(request.app.state, "sentence_explainer", None)


def _register_routes(app: FastAPI) -> None:
    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/debug/gcs")
    async def debug_gcs(
        settings: ServerSettings = Depends(get_settings),
    ) -> dict:
        """診斷端點：檢查 GCS 連線和認證狀態"""
        import os
        from google.cloud import storage

        result = {
            "env_vars": {},
            "secret_file": {},
            "gcs_connection": {},
            "settings": {},
        }

        # 檢查環境變數
        result["env_vars"]["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        result["env_vars"]["DATA_ROOT"] = os.getenv("DATA_ROOT")
        result["env_vars"]["STORYTELLING_GCS_CACHE_DIR"] = os.getenv("STORYTELLING_GCS_CACHE_DIR")
        result["env_vars"]["MEDIA_DELIVERY_MODE"] = os.getenv("MEDIA_DELIVERY_MODE")
        result["env_vars"]["GCS_MIRROR_INCLUDE_SUFFIXES"] = os.getenv("GCS_MIRROR_INCLUDE_SUFFIXES")

        # 檢查 secret file
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_path:
            result["secret_file"]["path"] = creds_path
            result["secret_file"]["exists"] = os.path.exists(creds_path)
            if os.path.exists(creds_path):
                try:
                    import json
                    with open(creds_path, 'r') as f:
                        creds_data = json.load(f)
                    result["secret_file"]["valid_json"] = True
                    result["secret_file"]["project_id"] = creds_data.get("project_id")
                    result["secret_file"]["client_email"] = creds_data.get("client_email")
                    result["secret_file"]["type"] = creds_data.get("type")
                except Exception as e:
                    result["secret_file"]["error"] = str(e)

        # 檢查 settings
        result["settings"]["data_root_raw"] = settings.data_root_raw
        result["settings"]["data_root"] = str(settings.data_root)
        result["settings"]["is_gcs_uri"] = is_gcs_uri(settings.data_root_raw)
        result["settings"]["media_delivery_mode"] = settings.media_delivery_mode
        result["settings"]["gcs_mirror_include_suffixes"] = settings.gcs_mirror_include_suffixes

        # 測試 GCS 連線
        if is_gcs_uri(settings.data_root_raw):
            try:
                bucket_name, prefix = parse_gcs_uri(settings.data_root_raw)
                result["gcs_connection"]["bucket"] = bucket_name
                result["gcs_connection"]["prefix"] = prefix

                # 嘗試建立 client
                client = storage.Client()
                result["gcs_connection"]["client_created"] = True
                result["gcs_connection"]["client_project"] = client.project

                # 嘗試列出 bucket
                bucket = client.bucket(bucket_name)
                result["gcs_connection"]["bucket_exists"] = bucket.exists()

                # 嘗試列出前 5 個 blob
                blobs = list(client.list_blobs(bucket, prefix=prefix + "/", max_results=5))
                result["gcs_connection"]["blob_count_sample"] = len(blobs)
                result["gcs_connection"]["sample_blobs"] = [blob.name for blob in blobs]

            except Exception as e:
                result["gcs_connection"]["error"] = str(e)
                result["gcs_connection"]["error_type"] = type(e).__name__

        return result

    @app.get("/books", response_model=List[BookItem], response_model_exclude_none=True)
    async def list_books(
        request: Request,
        cache: OutputDataCache = Depends(get_cache),
    ) -> List[BookItem]:
        books = cache.get_books()
        return [_to_book_item(book, request) for book in books.values()]

    @app.get("/books/{book_id}", response_model=BookItem, response_model_exclude_none=True)
    async def get_book(
        book_id: str,
        response: Response,
        request: Request,
        cache: OutputDataCache = Depends(get_cache),
    ) -> BookItem:
        book = cache.get_book(book_id)
        if not book:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

        etag = _build_book_etag(book)
        if etag:
            response.headers["ETag"] = etag
        return _to_book_item(book, request)

    @app.get("/books/{book_id}/assets", response_model=AssetList)
    async def list_book_assets(
        book_id: str,
        cache: OutputDataCache = Depends(get_cache),
    ) -> AssetList:
        """List all available assets for a book."""
        book = cache.get_book(book_id)
        if not book:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

        asset_names: set[str] = set()
        asset_names.update(book.assets.keys())
        asset_names.update(book.assets_remote_uris.keys())

        return AssetList(assets=sorted(asset_names))

    @app.api_route("/books/{book_id}/assets/{asset_name}", methods=["GET", "HEAD"])
    async def get_book_asset(
        book_id: str,
        asset_name: str,
        cache: OutputDataCache = Depends(get_cache),
        settings: ServerSettings = Depends(get_settings),
    ) -> Response:
        """Get a specific asset file for a book."""
        book = cache.get_book(book_id)
        if not book:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

        has_local = asset_name in book.assets
        has_remote = asset_name in book.assets_remote_uris

        if not has_local and not has_remote:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

        # Handle gcs-public mode
        if settings.media_delivery_mode == "gcs-public":
            if has_remote:
                remote_uri = book.assets_remote_uris[asset_name]
                public_url = _as_public_gcs_url(remote_uri)
                if not public_url:
                    logger.error("Unsupported asset URI for gcs-public: %s", remote_uri)
                    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid asset URI")
                return Response(status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": public_url})
            else:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not available remotely")

        # Serve local file
        if not has_local:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset file missing")

        asset_path = book.assets[asset_name]
        if not asset_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset file missing")

        # Determine content type based on extension
        content_type = _guess_content_type(asset_path)

        try:
            content = asset_path.read_bytes()
        except OSError:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to read asset")

        return Response(content=content, media_type=content_type)

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

    @app.get("/books/{book_id}/chapters/{chapter_id}/assets", response_model=AssetList)
    async def list_chapter_assets(
        book_id: str,
        chapter_id: str,
        cache: OutputDataCache = Depends(get_cache),
    ) -> AssetList:
        """List all available assets for a chapter."""
        chapter = cache.get_chapter(book_id, chapter_id)
        if not chapter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

        asset_names: set[str] = set()
        asset_names.update(chapter.assets.keys())
        asset_names.update(chapter.assets_remote_uris.keys())

        return AssetList(assets=sorted(asset_names))

    @app.api_route("/books/{book_id}/chapters/{chapter_id}/assets/{asset_name}", methods=["GET", "HEAD"])
    async def get_chapter_asset(
        book_id: str,
        chapter_id: str,
        asset_name: str,
        cache: OutputDataCache = Depends(get_cache),
        settings: ServerSettings = Depends(get_settings),
    ) -> Response:
        """Get a specific asset file for a chapter."""
        chapter = cache.get_chapter(book_id, chapter_id)
        if not chapter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

        has_local = asset_name in chapter.assets
        has_remote = asset_name in chapter.assets_remote_uris

        if not has_local and not has_remote:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

        # Handle gcs-public mode
        if settings.media_delivery_mode == "gcs-public":
            if has_remote:
                remote_uri = chapter.assets_remote_uris[asset_name]
                public_url = _as_public_gcs_url(remote_uri)
                if not public_url:
                    logger.error("Unsupported asset URI for gcs-public: %s", remote_uri)
                    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid asset URI")
                return Response(status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": public_url})
            else:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not available remotely")

        # Serve local file
        if not has_local:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset file missing")

        asset_path = chapter.assets[asset_name]
        if not asset_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset file missing")

        # Determine content type based on extension
        content_type = _guess_content_type(asset_path)

        try:
            content = asset_path.read_bytes()
        except OSError:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to read asset")

        return Response(content=content, media_type=content_type)

    @app.api_route("/books/{book_id}/chapters/{chapter_id}/audio", methods=["GET", "HEAD"])
    async def stream_audio(
        book_id: str,
        chapter_id: str,
        request: Request,
        cache: OutputDataCache = Depends(get_cache),
        settings: ServerSettings = Depends(get_settings),
    ) -> Response:
        chapter = cache.get_chapter(book_id, chapter_id)
        if not chapter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

        if settings.media_delivery_mode == "gcs-signed":
            if not chapter.audio_remote_uri:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not available")
            try:
                signed_url = generate_signed_url(
                    chapter.audio_remote_uri,
                    settings.signed_url_ttl_seconds,
                    response_content_type=chapter.audio_mime_type or "application/octet-stream",
                )
            except Exception as exc:  # pragma: no cover - depends on cloud IAM
                logger.exception("Failed to generate signed URL for audio")
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to sign audio URL") from exc
            return Response(status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": signed_url})

        if settings.media_delivery_mode == "gcs-public":
            if not chapter.audio_remote_uri:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not available")
            public_url = _as_public_gcs_url(chapter.audio_remote_uri)
            if not public_url:
                logger.error("Unsupported audio URI for gcs-public: %s", chapter.audio_remote_uri)
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid audio URI")
            return Response(status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": public_url})

        if not chapter.audio_file:
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

    @app.api_route("/books/{book_id}/chapters/{chapter_id}/subtitles", methods=["GET", "HEAD"], response_class=PlainTextResponse)
    async def get_subtitles(
        book_id: str,
        chapter_id: str,
        cache: OutputDataCache = Depends(get_cache),
        settings: ServerSettings = Depends(get_settings),
    ):
        chapter = cache.get_chapter(book_id, chapter_id)
        if not chapter or not chapter.subtitles:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtitles not available")

        if settings.media_delivery_mode == "gcs-signed":
            if not chapter.subtitles_remote_uri:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtitles not available")
            try:
                signed_url = generate_signed_url(
                    chapter.subtitles_remote_uri,
                    settings.signed_url_ttl_seconds,
                    response_content_type="text/plain; charset=utf-8",
                )
            except Exception as exc:  # pragma: no cover - depends on cloud IAM
                logger.exception("Failed to generate signed URL for subtitles")
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to sign subtitles URL") from exc
            return PlainTextResponse(
                "",
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": signed_url},
            )

        if settings.media_delivery_mode == "gcs-public":
            if not chapter.subtitles_remote_uri:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtitles not available")
            public_url = _as_public_gcs_url(chapter.subtitles_remote_uri)
            if not public_url:
                logger.error("Unsupported subtitles URI for gcs-public: %s", chapter.subtitles_remote_uri)
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid subtitles URI")
            return PlainTextResponse(
                "",
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": public_url},
            )

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

    @app.post("/explain/sentence", response_model=SentenceExplanationResponse)
    async def explain_sentence(
        payload: SentenceExplanationRequest,
        explanation_service: Optional[SentenceExplanationService] = Depends(get_sentence_explainer),
    ) -> SentenceExplanationResponse:
        if not explanation_service:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Sentence explanation unavailable")

        def _generate() -> SentenceExplanationResult:
            return explanation_service.explain_sentence(
                sentence=payload.sentence,
                previous_sentence=payload.previous_sentence or "",
                next_sentence=payload.next_sentence or "",
                language=payload.language or "zh-TW",
            )

        try:
            result = await run_in_threadpool(_generate)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except SentenceExplanationError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        vocabulary = [
            SentenceExplanationVocabulary(word=entry.word, meaning=entry.meaning, note=entry.note)
            for entry in result.vocabulary
        ]

        return SentenceExplanationResponse(
            overview=result.overview,
            key_points=list(result.key_points),
            vocabulary=vocabulary,
            cached=result.cached,
        )

    @app.post("/explain/phrase", response_model=SentenceExplanationResponse)
    async def explain_phrase(
        payload: PhraseExplanationRequest,
        explanation_service: Optional[SentenceExplanationService] = Depends(get_sentence_explainer),
    ) -> SentenceExplanationResponse:
        """解釋用戶在句子中選中的詞組用法。"""
        if not explanation_service:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Phrase explanation unavailable")

        def _generate() -> SentenceExplanationResult:
            return explanation_service.explain_phrase(
                phrase=payload.phrase,
                sentence=payload.sentence,
                previous_sentence=payload.previous_sentence or "",
                next_sentence=payload.next_sentence or "",
                language=payload.language or "zh-TW",
            )

        try:
            result = await run_in_threadpool(_generate)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except SentenceExplanationError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        vocabulary = [
            SentenceExplanationVocabulary(word=entry.word, meaning=entry.meaning, note=entry.note)
            for entry in result.vocabulary
        ]

        return SentenceExplanationResponse(
            overview=result.overview,
            key_points=list(result.key_points),
            vocabulary=vocabulary,
            cached=result.cached,
        )

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



def _to_book_item(book: BookData, request: Optional[Request] = None) -> BookItem:
    title = str(book.metadata.get("book_name") or book.id)
    cover_url = book.cover_url

    if cover_url:
        if cover_url.startswith("gs://"):
            http_url = _as_public_gcs_url(cover_url)
            if http_url:
                return BookItem(id=book.id, title=title, cover_url=http_url)
        return BookItem(id=book.id, title=title, cover_url=cover_url)

    # Fall back to local asset URL when running in local mode.
    if request and (book.assets or book.assets_remote_uris):
        for candidate in ("cover.jpg", "cover.png", "cover.webp"):
            if candidate in book.assets or candidate in book.assets_remote_uris:
                base = str(request.base_url).rstrip("/")
                encoded_book = quote(book.id, safe="")
                encoded_asset = quote(candidate, safe="")
                asset_url = f"{base}/books/{encoded_book}/assets/{encoded_asset}"
                return BookItem(id=book.id, title=title, cover_url=asset_url)

    return BookItem(id=book.id, title=title)


def _to_chapter_item(chapter: ChapterData) -> ChapterItem:
    return ChapterItem(
        id=chapter.id,
        title=chapter.title,
        chapter_number=chapter.number,
        audio_available=(chapter.audio_file is not None) or (chapter.audio_remote_uri is not None),
        subtitles_available=(
            chapter.subtitles is not None
            and (chapter.subtitles.srt_path is not None or chapter.subtitles.remote_uri is not None)
        ),
        word_count=chapter.word_count,
        audio_duration_sec=chapter.audio_duration_sec,
        words_per_minute=chapter.words_per_minute,
    )


def _to_chapter_playback(request: Request, book_id: str, chapter: ChapterData) -> ChapterPlayback:
    audio_url: Optional[str] = None
    if chapter.audio_file or chapter.audio_remote_uri:
        audio_url = str(request.url_for("stream_audio", book_id=book_id, chapter_id=chapter.id))

    subtitles_url: Optional[str] = None
    if chapter.subtitles and (chapter.subtitles.srt_path or chapter.subtitles.remote_uri):
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
