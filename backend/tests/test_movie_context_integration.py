import asyncio
import uuid

import pytest
from sqlalchemy import func, select

from app.models.movie_context import MovieContextTtsFallback
from app.services import llm_service, movie_context_service
from tests.test_rearrange_integration import _login, client, session_factory  # noqa: F401

# LLM và TTS được thay bằng bản giả (test luật tìm/lưu/cache/quyền sở hữu, không tốn quota);
# DB là Postgres thật như các integration test khác.


@pytest.fixture
def fakes(monkeypatch, tmp_path):
    sentences = [f"Well, {uuid.uuid4().hex[:8]} you can say that again, my friend." for _ in range(3)]
    tts_calls: list[str] = []

    async def fake_sentences(phrase: str, count: int = 3) -> list[str]:
        return sentences

    def fake_synthesize(text: str, persona) -> bytes:
        tts_calls.append(text)
        return b"RIFFfakewav"

    monkeypatch.setattr(llm_service, "generate_movie_example_sentences", fake_sentences)
    monkeypatch.setattr(movie_context_service, "_synthesize", fake_synthesize)
    monkeypatch.setattr(movie_context_service, "_audio_dir", lambda: tmp_path)
    return tts_calls, sentences


def test_search_save_and_audio(client, fakes) -> None:
    headers = _login(client)
    response = client.get("/api/movie-context/search", headers=headers, params={"phrase": "you can say that again"})
    assert response.status_code == 200
    matches = response.json()["matches"]
    assert len(matches) == 3
    assert {m["source_type"] for m in matches} == {"tts_fallback"}
    assert not any(m["is_saved"] for m in matches)

    match_id = matches[0]["match_id"]
    audio = client.get(matches[0]["audio_url"], headers=headers)
    assert audio.status_code == 200
    assert audio.content == b"RIFFfakewav"

    assert client.post(f"/api/movie-context/matches/{match_id}/save", headers=headers).status_code == 204
    # Lưu lặp lại vẫn ổn (idempotent).
    assert client.post(f"/api/movie-context/matches/{match_id}/save", headers=headers).status_code == 204


def test_other_user_cannot_touch_match(client, fakes) -> None:
    owner, intruder = _login(client), _login(client)
    match = client.get("/api/movie-context/search", headers=owner, params={"phrase": "hang out"}).json()["matches"][0]
    assert client.post(f"/api/movie-context/matches/{match['match_id']}/save", headers=intruder).status_code == 404
    assert client.get(match["audio_url"], headers=intruder).status_code == 404


def test_same_sentences_reuse_cached_audio(client, session_factory, fakes) -> None:
    tts_calls, sentences = fakes
    headers = _login(client)
    for _ in range(2):
        assert client.get("/api/movie-context/search", headers=headers, params={"phrase": "hang out"}).status_code == 200
    # Lần 2 trùng câu + persona NULL -> không TTS lại, không thêm dòng cache.
    assert len(tts_calls) == 3

    async def count_rows() -> int:
        async with session_factory() as session:
            return await session.scalar(
                select(func.count())
                .select_from(MovieContextTtsFallback)
                .where(MovieContextTtsFallback.phrase_text.in_(sentences))
            )

    assert asyncio.run(count_rows()) == 3


def test_requires_auth_and_phrase(client, fakes) -> None:
    assert client.get("/api/movie-context/search", params={"phrase": "x"}).status_code == 401
    headers = _login(client)
    assert client.get("/api/movie-context/search", headers=headers, params={"phrase": "   "}).status_code == 422
