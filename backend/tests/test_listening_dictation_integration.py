# Test tích hợp Dictation qua API thật + Postgres Docker thật (không mock DB) — cùng pattern
# với test_writing_integration.py/test_reading_classic_integration.py. Podcast/transcript
# được seed thẳng qua DB (không qua endpoint tạo Podcast — chưa build, cần ElevenLabs/Azure
# Speech key thật, xem lumina_context.md mục 3.12/4) kèm 1 file WAV thật (im lặng, PCM 16-bit)
# để speech_service.slice_wav_segment cắt thật, không phải giả lập.
import asyncio
import struct
import uuid
import wave
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.database import get_db
from app.main import app
from app.models.adaptive import UserError
from app.models.listening import DictationAttempt, Podcast, TranscriptSegment
from app.models.notebook import Document

WORDS = ["The", "quick", "brown", "fox", "jumps", "over", "the", "lazy", "dog"]
WORD_DURATION_MS = 500
SAMPLE_RATE = 16000


@pytest.fixture
def listening_client() -> Generator[TestClient, None, None]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())


def login(client: TestClient) -> tuple[dict[str, str], str]:
    email = f"listening_{uuid.uuid4().hex[:12]}@example.com"
    assert client.post(
        "/api/auth/register",
        json={"email": email, "password": "StrongPass123", "target_level": "b1"},
    ).status_code == 201
    response = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123"})
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    user = client.get("/api/users/me", headers=headers).json()
    return headers, user["id"]


def _write_silent_wav(path: Path, duration_ms: int) -> None:
    # File WAV PCM thật (im lặng) — đủ để speech_service.slice_wav_segment đọc/cắt thật bằng
    # module wave chuẩn, không cần audio có nội dung nghe được cho mục đích test thuật toán.
    frame_count = int(SAMPLE_RATE * duration_ms / 1000)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(struct.pack(f"<{frame_count}h", *([0] * frame_count)))


async def _seed_podcast(user_id: str, words: list[str] = WORDS) -> tuple[str, Path]:
    """Tạo 1 document + podcast (status=ready) + transcript_segments cấp từ, mỗi từ dài
    WORD_DURATION_MS liên tiếp từ 0 — và 1 file WAV thật cho podcast.audio_url."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    audio_path = (
        Path(__file__).resolve().parents[1]
        / settings.storage_audio_dir
        / f"test_podcast_{uuid.uuid4().hex[:8]}.wav"
    )
    _write_silent_wav(audio_path, len(words) * WORD_DURATION_MS)

    async with factory() as session:
        document = Document(
            user_id=uuid.UUID(user_id), title="Test Podcast Source", source_type="audio", status="ready"
        )
        session.add(document)
        await session.flush()

        podcast = Podcast(
            document_id=document.id,
            script_text=" ".join(words),
            audio_url=str(audio_path),
            status="ready",
        )
        session.add(podcast)
        await session.flush()

        for index, word in enumerate(words):
            session.add(
                TranscriptSegment(
                    podcast_id=podcast.id,
                    word_index=index,
                    word_text=word,
                    start_time_ms=index * WORD_DURATION_MS,
                    end_time_ms=(index + 1) * WORD_DURATION_MS,
                )
            )
        await session.commit()
        podcast_id = str(podcast.id)
    await engine.dispose()
    return podcast_id, audio_path


async def _count_user_errors(user_id: str) -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        result = await session.execute(select(UserError).where(UserError.user_id == uuid.UUID(user_id)))
        rows = list(result.scalars().all())
    await engine.dispose()
    return len(rows)


async def _mark_podcast_not_ready(podcast_id: str) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await session.execute(
            update(Podcast).where(Podcast.id == uuid.UUID(podcast_id)).values(status="processing")
        )
        await session.commit()
    await engine.dispose()


def test_create_dictation_attempt_without_segment_range_covers_whole_transcript(
    listening_client: TestClient,
) -> None:
    headers, user_id = login(listening_client)
    podcast_id, _ = asyncio.run(_seed_podcast(user_id))

    created = listening_client.post(
        "/api/listening/dictation", headers=headers, json={"podcast_id": podcast_id}
    )
    assert created.status_code == 201
    body = created.json()
    assert body["attempt_id"]
    # Cắt audio thật đã chạy — file tồn tại trên đĩa, không phải giá trị giả.
    audio = listening_client.get(body["audio_url"], headers=headers)
    assert audio.status_code == 200 and audio.content[:4] == b"RIFF"

    # Vì transcript ngắn hơn DEFAULT_SEGMENT_SECONDS (20s), toàn bộ 9 từ đều nằm trong đoạn —
    # nộp đúng nguyên câu phải cho điểm tuyệt đối 100.
    submitted = listening_client.post(
        f"/api/listening/dictation/{body['attempt_id']}/submit",
        headers=headers,
        json={"transcribed_text": " ".join(WORDS)},
    )
    assert submitted.status_code == 200
    assert submitted.json() == {"score": 100.0, "errors": []}


def test_create_dictation_attempt_with_explicit_segment_range_limits_reference_words(
    listening_client: TestClient,
) -> None:
    headers, user_id = login(listening_client)
    podcast_id, _ = asyncio.run(_seed_podcast(user_id))

    # Chỉ lấy 3 từ giữa: "brown"(1000-1500), "fox"(1500-2000), "jumps"(2000-2500).
    created = listening_client.post(
        "/api/listening/dictation",
        headers=headers,
        json={"podcast_id": podcast_id, "segment_range": {"start_ms": 1000, "end_ms": 2500}},
    )
    assert created.status_code == 201
    attempt_id = created.json()["attempt_id"]

    submitted = listening_client.post(
        f"/api/listening/dictation/{attempt_id}/submit",
        headers=headers,
        json={"transcribed_text": "brown fox jumps"},
    )
    assert submitted.status_code == 200
    assert submitted.json() == {"score": 100.0, "errors": []}


def test_submit_reports_missing_extra_and_wrong_words_and_persists_user_errors(
    listening_client: TestClient,
) -> None:
    headers, user_id = login(listening_client)
    podcast_id, _ = asyncio.run(_seed_podcast(user_id, words=["I", "was", "very", "hungry"]))

    created = listening_client.post(
        "/api/listening/dictation", headers=headers, json={"podcast_id": podcast_id}
    )
    attempt_id = created.json()["attempt_id"]

    # "was" bị bỏ (missing), "hungry" nghe nhầm hẳn thành "banana" (wrong, phonetically far),
    # thêm "please" (extra) không có trong transcript gốc.
    submitted = listening_client.post(
        f"/api/listening/dictation/{attempt_id}/submit",
        headers=headers,
        json={"transcribed_text": "I very banana please"},
    )
    assert submitted.status_code == 200
    body = submitted.json()
    error_types = {error["type"] for error in body["errors"]}
    assert error_types == {"missing", "wrong", "extra"}
    assert body["score"] < 100.0

    # 2 lỗi phân loại được (missing "was" + wrong "hungry") phải ghi thật vào user_errors;
    # "extra" không ghi (không có từ gốc để phân loại) — xem dictation_grading.diff_dictation.
    assert asyncio.run(_count_user_errors(user_id)) == 2


def test_resubmitting_same_attempt_is_idempotent_and_does_not_duplicate_user_errors(
    listening_client: TestClient,
) -> None:
    headers, user_id = login(listening_client)
    podcast_id, _ = asyncio.run(_seed_podcast(user_id, words=["Hello", "world"]))
    created = listening_client.post(
        "/api/listening/dictation", headers=headers, json={"podcast_id": podcast_id}
    )
    attempt_id = created.json()["attempt_id"]

    first = listening_client.post(
        f"/api/listening/dictation/{attempt_id}/submit",
        headers=headers,
        json={"transcribed_text": "Hello banana"},
    )
    assert first.status_code == 200
    error_count_after_first = asyncio.run(_count_user_errors(user_id))
    assert error_count_after_first >= 1

    # Nộp lại với text khác hẳn — vì đã completed (diff_result != None), phải trả lại kết quả
    # CŨ nguyên vẹn, không chấm lại/không ghi thêm user_errors.
    second = listening_client.post(
        f"/api/listening/dictation/{attempt_id}/submit",
        headers=headers,
        json={"transcribed_text": "a completely different sentence"},
    )
    assert second.status_code == 200
    assert second.json() == first.json()
    assert asyncio.run(_count_user_errors(user_id)) == error_count_after_first


def test_blank_submission_marks_every_word_as_missing(listening_client: TestClient) -> None:
    headers, user_id = login(listening_client)
    podcast_id, _ = asyncio.run(_seed_podcast(user_id, words=["One", "two", "three"]))
    created = listening_client.post(
        "/api/listening/dictation", headers=headers, json={"podcast_id": podcast_id}
    )
    attempt_id = created.json()["attempt_id"]

    submitted = listening_client.post(
        f"/api/listening/dictation/{attempt_id}/submit",
        headers=headers,
        json={"transcribed_text": ""},
    )
    assert submitted.status_code == 200
    body = submitted.json()
    assert body["score"] == 0.0
    assert len(body["errors"]) == 3
    assert all(error["type"] == "missing" for error in body["errors"])


def test_create_dictation_for_nonexistent_podcast_returns_not_found(listening_client: TestClient) -> None:
    headers, _ = login(listening_client)
    response = listening_client.post(
        "/api/listening/dictation", headers=headers, json={"podcast_id": str(uuid.uuid4())}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "podcast_not_found"


def test_create_dictation_for_another_users_podcast_returns_not_found(listening_client: TestClient) -> None:
    _, owner_id = login(listening_client)
    podcast_id, _ = asyncio.run(_seed_podcast(owner_id))

    other_headers, _ = login(listening_client)
    response = listening_client.post(
        "/api/listening/dictation", headers=other_headers, json={"podcast_id": podcast_id}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "podcast_not_found"


def test_create_dictation_for_not_ready_podcast_returns_400(listening_client: TestClient) -> None:
    headers, user_id = login(listening_client)
    podcast_id, _ = asyncio.run(_seed_podcast(user_id))
    asyncio.run(_mark_podcast_not_ready(podcast_id))

    response = listening_client.post(
        "/api/listening/dictation", headers=headers, json={"podcast_id": podcast_id}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "podcast_not_ready"


def test_submit_from_another_user_returns_not_found(listening_client: TestClient) -> None:
    owner_headers, owner_id = login(listening_client)
    podcast_id, _ = asyncio.run(_seed_podcast(owner_id, words=["Hello", "world"]))
    created = listening_client.post(
        "/api/listening/dictation", headers=owner_headers, json={"podcast_id": podcast_id}
    )
    attempt_id = created.json()["attempt_id"]

    other_headers, _ = login(listening_client)
    response = listening_client.post(
        f"/api/listening/dictation/{attempt_id}/submit",
        headers=other_headers,
        json={"transcribed_text": "Hello world"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "dictation_attempt_not_found"


def test_reference_word_tags_flag_rare_and_proper_words_at_creation(listening_client: TestClient) -> None:
    headers, user_id = login(listening_client)
    # "Paris" cố ý KHÔNG ở đầu câu (index 0 luôn được coi là đầu câu, không tính viết hoa đầu
    # câu là dấu hiệu tên riêng — feature-listening.md mục 3.5) để test đúng nhánh proper noun.
    podcast_id, _ = asyncio.run(
        _seed_podcast(user_id, words=["The", "museum", "is", "in", "Paris", "and", "has", "mitochondria", "exhibits"])
    )
    created = listening_client.post(
        "/api/listening/dictation", headers=headers, json={"podcast_id": podcast_id}
    )
    attempt_id = created.json()["attempt_id"]

    async def load_tags() -> list[dict]:
        settings = get_settings()
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            attempt = await session.get(DictationAttempt, uuid.UUID(attempt_id))
            tags = attempt.reference_word_tags
        await engine.dispose()
        return tags

    tags = asyncio.run(load_tags())
    tags_by_word = {tag["word"]: tag["is_rare_or_proper"] for tag in tags}
    assert tags_by_word["Paris"] is True  # tên riêng, không ở đầu câu
    assert tags_by_word["has"] is False
    assert tags_by_word["mitochondria"] is True  # từ hiếm
