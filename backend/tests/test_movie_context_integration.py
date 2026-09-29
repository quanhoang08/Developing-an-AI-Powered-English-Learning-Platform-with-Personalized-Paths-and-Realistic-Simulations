import asyncio
import random
import string
import uuid

import pytest
from sqlalchemy import delete, func, select

from app.models.movie_context import MovieContextMatch, MovieContextTtsFallback, VideoSource, VideoSubtitleIndex
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


def test_video_match_preferred_over_tts_and_served(client, session_factory, fakes, monkeypatch, tmp_path) -> None:
    # Có dòng phụ đề khớp -> trả real_video (kèm mốc thời gian), KHÔNG sinh TTS; video chỉ chủ sở hữu tải được.
    tts_calls, _ = fakes
    token = "".join(random.choices(string.ascii_lowercase, k=10))
    (tmp_path / "clip.mp4").write_bytes(b"FAKEMP4")
    monkeypatch.setattr(movie_context_service, "video_dir", lambda: tmp_path)

    async def seed() -> uuid.UUID:
        async with session_factory() as session:
            source = VideoSource(title="Test scene", platform="test", video_url="clip.mp4")
            session.add(source)
            await session.flush()
            session.add(
                VideoSubtitleIndex(
                    video_source_id=source.id,
                    phrase_text=f"He said the {token} plan was a total disaster.",
                    start_time_ms=1000,
                    end_time_ms=4200,
                )
            )
            session.add(VideoSubtitleIndex(video_source_id=source.id, phrase_text="Nobody moved.", start_time_ms=500, end_time_ms=900))
            # Dòng khác cũng chứa cụm -> cũng phải được tô (nhưng không phải dòng của match).
            session.add(
                VideoSubtitleIndex(
                    video_source_id=source.id, phrase_text=f"Yes, THE {token} plan!", start_time_ms=5000, end_time_ms=6000
                )
            )
            await session.commit()
            return source.id

    async def cleanup(source_id: uuid.UUID) -> None:
        async with session_factory() as session:
            lines = select(VideoSubtitleIndex.id).where(VideoSubtitleIndex.video_source_id == source_id)
            await session.execute(delete(MovieContextMatch).where(MovieContextMatch.video_subtitle_index_id.in_(lines)))
            await session.execute(delete(VideoSource).where(VideoSource.id == source_id))
            await session.commit()

    source_id = asyncio.run(seed())
    try:
        owner, intruder = _login(client), _login(client)
        response = client.get("/api/movie-context/search", headers=owner, params={"phrase": f"the {token} plan"})
        assert response.status_code == 200
        matches = response.json()["matches"]
        assert len(matches) == 2  # cả hai dòng chứa cụm; kiểm tra chi tiết trên dòng ở 1000ms
        match = next(m for m in matches if m["start_ms"] == 1000)
        assert match["source_type"] == "real_video"
        assert match["title"] == "Test scene"
        assert (match["start_ms"], match["end_ms"]) == (1000, 4200)
        assert match["audio_url"] is None and match["video_url"].endswith("/video")
        assert tts_calls == []

        video = client.get(match["video_url"], headers=owner)
        assert video.status_code == 200 and video.content == b"FAKEMP4"
        assert video.headers["content-type"] == "video/mp4"
        assert client.get(match["video_url"], headers=intruder).status_code == 404
        # Match video không có audio TTS.
        audio_url = match["video_url"].replace("/video", "/audio")
        assert client.get(audio_url, headers=owner).status_code == 404
        assert client.post(f"/api/movie-context/matches/{match['match_id']}/save", headers=owner).status_code == 204

        # Phụ đề: đủ mọi dòng của video theo thời gian, chỉ dòng chứa cụm tìm được đánh dấu is_match.
        subtitles_url = match["video_url"].replace("/video", "/subtitles")
        cues = client.get(subtitles_url, headers=owner).json()
        assert [(c["start_ms"], c["is_match"]) for c in cues] == [(500, False), (1000, True), (5000, True)]
        assert cues[0]["text"] == "Nobody moved."
        assert client.get(subtitles_url, headers=intruder).status_code == 404
    finally:
        asyncio.run(cleanup(source_id))


def test_no_video_match_falls_back_to_tts(client, fakes) -> None:
    # Cụm không có trong kho video -> vẫn ra 3 câu TTS như trước.
    headers = _login(client)
    matches = client.get("/api/movie-context/search", headers=headers, params={"phrase": "hang out"}).json()["matches"]
    assert len(matches) == 3 and {m["source_type"] for m in matches} == {"tts_fallback"}
    assert all(m["audio_url"] and m["video_url"] is None for m in matches)


def test_requires_auth_and_phrase(client, fakes) -> None:
    assert client.get("/api/movie-context/search", params={"phrase": "x"}).status_code == 401
    headers = _login(client)
    assert client.get("/api/movie-context/search", headers=headers, params={"phrase": "   "}).status_code == 422
