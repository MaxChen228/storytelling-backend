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
from server.app.services import (
    ChapterData,
    SentenceExplanationResult,
    SubtitleData,
    VocabularyEntry,
)


class DummyExplanationService:
    def __init__(self) -> None:
        self.sentence_calls = []
        self.phrase_calls = []

    def explain_sentence(
        self,
        sentence: str,
        previous_sentence: str = "",
        next_sentence: str = "",
        language: str = "zh-TW",
    ) -> SentenceExplanationResult:
        self.sentence_calls.append((sentence, previous_sentence, next_sentence, language))
        return SentenceExplanationResult(
            overview=f"{sentence}-overview",
            key_points=("重點 A", "重點 B"),
            vocabulary=(
                VocabularyEntry(word="sample", meaning="範例", note=None),
            ),
            chinese_meaning=f"{sentence}-中文解釋",
            cached=False,
        )

    def explain_phrase(
        self,
        phrase: str,
        sentence: str,
        previous_sentence: str = "",
        next_sentence: str = "",
        language: str = "zh-TW",
    ) -> SentenceExplanationResult:
        self.phrase_calls.append((phrase, sentence, previous_sentence, next_sentence, language))
        # 模擬快取:第二次相同請求回傳 cached=True
        is_cached = len([c for c in self.phrase_calls if c == (phrase, sentence, previous_sentence, next_sentence, language)]) > 1
        return SentenceExplanationResult(
            overview=f"「{phrase}」在句子中的用法解釋",
            key_points=(f"{phrase} 的搭配規則", f"{phrase} 的語法作用"),
            vocabulary=(
                VocabularyEntry(word=phrase.split()[0] if phrase else "word", meaning="詞義", note="補充說明"),
            ),
            chinese_meaning=f"{phrase}-中文解釋",
            cached=is_cached,
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
    app.state.sentence_explainer = DummyExplanationService()
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


def test_sentence_explanation_endpoint(test_client: TestClient) -> None:
    response = test_client.post(
        "/explain/sentence",
        json={
            "sentence": "Hello world",
            "previous_sentence": "Good morning everyone.",
            "next_sentence": "Let's begin our story.",
            "language": "zh-TW",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["overview"] == "Hello world-overview"
    assert payload["chinese_meaning"] == "Hello world-中文解釋"
    assert payload["key_points"] == ["重點 A", "重點 B"]
    assert payload["vocabulary"][0]["word"] == "sample"


def test_phrase_explanation_success(test_client: TestClient) -> None:
    """測試正常詞組解釋請求。"""
    response = test_client.post(
        "/explain/phrase",
        json={
            "phrase": "so glad",
            "sentence": "I am so glad you are here with me today.",
            "previous_sentence": "Good morning everyone.",
            "next_sentence": "Let's begin our story.",
            "language": "zh-TW",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "so glad" in payload["overview"]
    assert payload["chinese_meaning"] == "so glad-中文解釋"
    assert len(payload["key_points"]) == 2
    assert payload["key_points"][0] == "so glad 的搭配規則"
    assert payload["vocabulary"][0]["word"] == "so"
    assert payload["cached"] is False


def test_phrase_explanation_cached(test_client: TestClient) -> None:
    """測試詞組解釋的快取功能。"""
    request_data = {
        "phrase": "so happy",
        "sentence": "I am so happy to see you.",
        "previous_sentence": "",
        "next_sentence": "",
        "language": "zh-TW",
    }

    # 第一次請求
    response1 = test_client.post(
        "/explain/phrase",
        json=request_data,
    )
    assert response1.status_code == 200
    assert response1.json()["cached"] is False

    # 第二次相同請求應該命中快取
    response2 = test_client.post(
        "/explain/phrase",
        json=request_data,
    )
    assert response2.status_code == 200
    assert response2.json()["cached"] is True


def test_phrase_explanation_with_punctuation(test_client: TestClient) -> None:
    """測試包含標點符號的詞組(前端可能傳來帶標點的詞組)。"""
    response = test_client.post(
        "/explain/phrase",
        json={
            "phrase": "I'm",
            "sentence": "I'm glad to meet you.",
            "language": "zh-TW",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "I'm" in payload["overview"]


def test_phrase_explanation_empty_phrase(test_client: TestClient) -> None:
    """測試空詞組應該回傳 400 錯誤。"""
    response = test_client.post(
        "/explain/phrase",
        json={
            "phrase": "",
            "sentence": "Hello world",
            "language": "zh-TW",
        },
    )
    assert response.status_code == 422  # Pydantic validation error


def test_phrase_explanation_service_unavailable(test_client: TestClient) -> None:
    """測試服務不可用應該回傳 503 錯誤。"""
    app = test_client.app
    original = app.state.sentence_explainer
    app.state.sentence_explainer = None
    try:
        response = test_client.post(
            "/explain/phrase",
            json={
                "phrase": "hello",
                "sentence": "Hello world",
                "language": "zh-TW",
            },
        )
        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"].lower()
    finally:
        app.state.sentence_explainer = original


def test_stream_audio_signed_mode_redirect(monkeypatch: pytest.MonkeyPatch, test_client: TestClient) -> None:
    app = test_client.app
    original_cache = app.state.cache
    original_mode = app.state.settings.media_delivery_mode
    original_ttl = app.state.settings.signed_url_ttl_seconds
    app.state.settings.media_delivery_mode = "gcs-signed"
    app.state.settings.signed_url_ttl_seconds = 90

    chapter = ChapterData(
        id="chapter0",
        title="Remote chapter",
        number=1,
        path=Path("/tmp/remote"),
        metadata={},
        audio_file=None,
        audio_mime_type="audio/mpeg",
        subtitles=None,
        word_count=None,
        audio_duration_sec=None,
        words_per_minute=None,
        audio_remote_uri="gs://demo-bucket/demo.mp3",
        subtitles_remote_uri=None,
    )

    class DummyCache:
        def __init__(self, stored: ChapterData) -> None:
            self.stored = stored

        def get_chapter(self, book_id: str, chapter_id: str) -> ChapterData:
            assert book_id == "demo_book"
            assert chapter_id == "chapter0"
            return self.stored

    app.state.cache = DummyCache(chapter)

    captured: dict[str, object] = {}

    def fake_signed(url: str, ttl: int, *, response_content_type: str | None = None, response_disposition: str | None = None, method: str = "GET") -> str:
        captured["url"] = url
        captured["ttl"] = ttl
        captured["content_type"] = response_content_type
        return "https://signed.example/audio"

    monkeypatch.setattr("server.app.main.generate_signed_url", fake_signed)

    try:
        response = test_client.get(
            "/books/demo_book/chapters/chapter0/audio",
            follow_redirects=False,
        )
        assert response.status_code == 307, response.text
        assert response.headers["Location"] == "https://signed.example/audio"
        assert captured["url"] == "gs://demo-bucket/demo.mp3"
        assert captured["ttl"] == 90
        assert captured["content_type"] == "audio/mpeg"
    finally:
        app.state.cache = original_cache
        app.state.settings.media_delivery_mode = original_mode
        app.state.settings.signed_url_ttl_seconds = original_ttl


def test_get_subtitles_signed_mode_redirect(monkeypatch: pytest.MonkeyPatch, test_client: TestClient) -> None:
    app = test_client.app
    original_cache = app.state.cache
    original_mode = app.state.settings.media_delivery_mode
    original_ttl = app.state.settings.signed_url_ttl_seconds
    app.state.settings.media_delivery_mode = "gcs-signed"
    app.state.settings.signed_url_ttl_seconds = 120

    subtitle = SubtitleData(srt_path=None, remote_uri="gs://demo-bucket/demo.srt")
    chapter = ChapterData(
        id="chapter0",
        title="Remote chapter",
        number=1,
        path=Path("/tmp/remote"),
        metadata={},
        audio_file=None,
        audio_mime_type=None,
        subtitles=subtitle,
        word_count=None,
        audio_duration_sec=None,
        words_per_minute=None,
        audio_remote_uri=None,
        subtitles_remote_uri="gs://demo-bucket/demo.srt",
    )

    class DummyCache:
        def __init__(self, stored: ChapterData) -> None:
            self.stored = stored

        def get_chapter(self, book_id: str, chapter_id: str) -> ChapterData:
            return self.stored

    app.state.cache = DummyCache(chapter)

    captured: dict[str, object] = {}

    def fake_signed(url: str, ttl: int, *, response_content_type: str | None = None, response_disposition: str | None = None, method: str = "GET") -> str:
        captured["url"] = url
        captured["ttl"] = ttl
        captured["content_type"] = response_content_type
        return "https://signed.example/subtitles"

    monkeypatch.setattr("server.app.main.generate_signed_url", fake_signed)

    try:
        response = test_client.get(
            "/books/demo_book/chapters/chapter0/subtitles",
            follow_redirects=False,
        )
        assert response.status_code == 307, response.text
        assert response.headers["Location"] == "https://signed.example/subtitles"
        assert captured["url"] == "gs://demo-bucket/demo.srt"
        assert captured["content_type"] == "text/plain; charset=utf-8"
    finally:
        app.state.cache = original_cache
        app.state.settings.media_delivery_mode = original_mode
        app.state.settings.signed_url_ttl_seconds = original_ttl


def test_stream_audio_public_mode_redirect(test_client: TestClient) -> None:
    app = test_client.app
    original_cache = app.state.cache
    original_mode = app.state.settings.media_delivery_mode
    app.state.settings.media_delivery_mode = "gcs-public"

    chapter = ChapterData(
        id="chapter0",
        title="Remote chapter",
        number=1,
        path=Path("/tmp/remote"),
        metadata={},
        audio_file=None,
        audio_mime_type="audio/mpeg",
        subtitles=None,
        word_count=None,
        audio_duration_sec=None,
        words_per_minute=None,
        audio_remote_uri="gs://demo-bucket/path/podcast.mp3",
        subtitles_remote_uri=None,
    )

    class DummyCache:
        def __init__(self, stored: ChapterData) -> None:
            self.stored = stored

        def get_chapter(self, book_id: str, chapter_id: str) -> ChapterData:
            return self.stored

    app.state.cache = DummyCache(chapter)

    try:
        response = test_client.get(
            "/books/demo_book/chapters/chapter0/audio",
            follow_redirects=False,
        )
        assert response.status_code == 307
        assert response.headers["Location"] == "https://storage.googleapis.com/demo-bucket/path/podcast.mp3"
    finally:
        app.state.cache = original_cache
        app.state.settings.media_delivery_mode = original_mode


def test_get_subtitles_public_mode_redirect(test_client: TestClient) -> None:
    app = test_client.app
    original_cache = app.state.cache
    original_mode = app.state.settings.media_delivery_mode
    app.state.settings.media_delivery_mode = "gcs-public"

    subtitle = SubtitleData(srt_path=None, remote_uri="gs://demo-bucket/path/subtitles.srt")
    chapter = ChapterData(
        id="chapter0",
        title="Remote chapter",
        number=1,
        path=Path("/tmp/remote"),
        metadata={},
        audio_file=None,
        audio_mime_type=None,
        subtitles=subtitle,
        word_count=None,
        audio_duration_sec=None,
        words_per_minute=None,
        audio_remote_uri=None,
        subtitles_remote_uri="gs://demo-bucket/path/subtitles.srt",
    )

    class DummyCache:
        def __init__(self, stored: ChapterData) -> None:
            self.stored = stored

        def get_chapter(self, book_id: str, chapter_id: str) -> ChapterData:
            return self.stored

    app.state.cache = DummyCache(chapter)

    try:
        response = test_client.get(
            "/books/demo_book/chapters/chapter0/subtitles",
            follow_redirects=False,
        )
        assert response.status_code == 307
        assert response.headers["Location"] == "https://storage.googleapis.com/demo-bucket/path/subtitles.srt"
    finally:
        app.state.cache = original_cache
        app.state.settings.media_delivery_mode = original_mode


def test_sentence_explanation_without_output_files(tmp_path: Path) -> None:
    settings = ServerSettings(
        data_root=tmp_path,
        cors_origins=[],
        gzip_min_size=32,
    )
    app = create_app(settings)
    app.state.sentence_explainer = DummyExplanationService()
    client = TestClient(app)

    response = client.post(
        "/explain/sentence",
        json={
            "sentence": "Testing",
            "previous_sentence": "",
            "next_sentence": "",
            "language": "zh-TW",
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["overview"] == "Testing-overview"
    assert result["chinese_meaning"] == "Testing-中文解釋"
