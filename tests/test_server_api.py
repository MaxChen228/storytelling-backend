from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from server.app import ServerSettings, create_app
from server.app.services import TranslationResult


class DummyTranslationService:
    def __init__(self) -> None:
        self.calls = []

    def translate(self, text: str, target_language: str, source_language: str | None = None) -> TranslationResult:
        self.calls.append((text, target_language, source_language))
        return TranslationResult(
            translated_text=f"{text}-{target_language}",
            detected_source_language=source_language or "en",
            cached=False,
        )


@pytest.fixture
def sample_data(tmp_path: Path) -> Path:
    book_dir = tmp_path / "demo_book"
    chapter_dir = book_dir / "chapter0"
    chapter_dir.mkdir(parents=True)

    (book_dir / "book_metadata.json").write_text(
        json.dumps(
            {
                "book_name": "Demo Book",
                "updated_at": "20250101_010101",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    (book_dir / "chapters_index.json").write_text(
        json.dumps(
            {
                "chapter0": {
                    "chapter_number": 1,
                    "chapter_title": "chapter0",
                    "source_file": "data/demo/chapter0.txt",
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    sessions_dir = book_dir / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "audio_session_20250101.json").write_text(
        json.dumps(
            {
                "session_type": "audio_generation",
                "book_name": "demo_book",
                "timestamp": "20250101_010101",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    (chapter_dir / "metadata.json").write_text(
        json.dumps(
            {
                "timestamp": "20250101_010101",
                "chapter_number": 1,
                "chapter_title": "Warm up",
                "english_level": "beginner",
                "level_label": "Beginner friendly",
                "actual_words": 120,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    (chapter_dir / "podcast_script.txt").write_text(
        "Hello world script.\nThis is a sample chapter.",
        encoding="utf-8",
    )

    (chapter_dir / "podcast.wav").write_bytes(b"RIFFxxxxWAVEfmt ")

    (chapter_dir / "subtitles.srt").write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nHello world\n\n"
        "2\n00:00:02,000 --> 00:00:04,000\nSample chapter\n",
        encoding="utf-8",
    )

    (chapter_dir / "aligned_transcript.json").write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "start": 0.0,
                        "end": 2.0,
                        "text": "Hello world",
                        "words": [
                            {"word": "Hello", "start": 0.0, "end": 0.5, "score": 0.9},
                            {"word": "world", "start": 0.5, "end": 1.0, "score": 0.95},
                        ],
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def test_client(sample_data: Path) -> TestClient:
    settings = ServerSettings(
        data_root=sample_data,
        cors_origins=[],
        gzip_min_size=32,
    )
    app = create_app(settings)
    app.state.translation_service = DummyTranslationService()
    return TestClient(app)


def test_list_books(test_client: TestClient) -> None:
    response = test_client.get("/books")
    assert response.status_code == 200
    payload = response.json()
    assert payload and payload[0]["id"] == "demo_book"


def test_book_detail_returns_basic_info(test_client: TestClient) -> None:
    response = test_client.get("/books/demo_book")
    assert response.status_code == 200
    data = response.json()
    assert data == {"id": "demo_book", "title": "Demo Book"}
    assert "ETag" in response.headers


def test_chapter_playback_payload(test_client: TestClient) -> None:
    response = test_client.get("/books/demo_book/chapters/chapter0")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "chapter0"
    assert data["title"] == "Warm up"
    assert data["audio_url"].endswith("/books/demo_book/chapters/chapter0/audio")
    assert data["subtitles_url"].endswith("/books/demo_book/chapters/chapter0/subtitles")
    assert "ETag" in response.headers


def test_fetch_subtitles_as_srt(test_client: TestClient) -> None:
    response = test_client.get("/books/demo_book/chapters/chapter0/subtitles")
    assert response.status_code == 200
    assert "Hello world" in response.text
    assert response.headers["Content-Disposition"].startswith("inline; filename=")


def test_audio_range_request(test_client: TestClient) -> None:
    response = test_client.get(
        "/books/demo_book/chapters/chapter0/audio",
        headers={"Range": "bytes=0-3"},
    )
    assert response.status_code == 206
    assert response.headers["Content-Range"].startswith("bytes 0-3/")
    assert response.content == b"RIFF"


def test_transcript_endpoint_removed(test_client: TestClient) -> None:
    response = test_client.get("/books/demo_book/chapters/chapter0/transcript")
    assert response.status_code == 404


def test_translate_text_success(test_client: TestClient) -> None:
    response = test_client.post(
        "/translations",
        json={
            "text": "Hello world",
            "target_language_code": "zh-TW",
            "source_language_code": "en",
            "book_id": "demo_book",
            "chapter_id": "chapter0",
            "subtitle_id": 1,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["translated_text"] == "Hello world-zh-TW"
    assert payload["detected_source_language"] == "en"
    assert payload["cached"] is False


def test_translate_text_service_unavailable(test_client: TestClient) -> None:
    app = test_client.app
    original = app.state.translation_service
    app.state.translation_service = None
    try:
        response = test_client.post(
            "/translations",
            json={"text": "Hello", "target_language_code": "zh-TW"},
        )
        assert response.status_code == 503
    finally:
        app.state.translation_service = original
