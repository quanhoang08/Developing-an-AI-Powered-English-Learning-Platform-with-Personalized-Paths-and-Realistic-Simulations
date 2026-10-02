from app.services.podcast_service import locate_quote

WORDS = "The meeting was moved from Monday to Thursday because the manager is travelling".split()


def test_locate_quote_exact_and_fuzzy() -> None:
    assert locate_quote(WORDS, "moved from Monday to Thursday") == (3, 7)
    # STT nghe sai 1 từ vẫn định vị được; chữ hoa/dấu câu không ảnh hưởng.
    assert locate_quote(WORDS, "Moved from Monday, to Friday") == (3, 7)
    assert locate_quote(WORDS, "completely unrelated sentence here") is None
    assert locate_quote(WORDS, "") is None


# --- Endpoint thật (Postgres thật, LLM giả) ---
import asyncio

from app.services import llm_service
from tests.test_listening_dictation_integration import _seed_podcast, listening_client, login  # noqa: F401


def test_comprehension_endpoint_locates_evidence(listening_client, monkeypatch) -> None:
    async def fake(transcript: str, count: int) -> list[dict]:
        good = {
            "question": "What jumps?", "options": ["fox", "dog", "cat", "cow"], "correct_index": 0,
            "evidence_quote": "brown fox jumps over", "trap_note": "dog is heard too.",
        }
        return [good, {**good, "options": ["only", "two"]}]  # câu thứ 2 hỏng -> bị bỏ

    monkeypatch.setattr(llm_service, "generate_listening_questions", fake)
    headers, user_id = login(listening_client)
    podcast_id, _ = asyncio.run(_seed_podcast(user_id))
    response = listening_client.post(
        f"/api/listening/podcasts/{podcast_id}/comprehension", headers=headers, json={}
    )
    assert response.status_code == 200, response.text
    questions = response.json()["questions"]
    assert len(questions) == 1
    # "brown fox jumps over" = từ index 2..5, mỗi từ 500ms.
    assert (questions[0]["evidence_start_ms"], questions[0]["evidence_end_ms"]) == (1000, 3000)


def test_quiz_submit_grades_records_errors_and_is_idempotent(listening_client, monkeypatch) -> None:
    async def fake(transcript: str, count: int) -> list[dict]:
        base = {"options": ["fox", "dog", "cat", "cow"], "correct_index": 0, "trap_note": "dog is heard too."}
        return [
            {**base, "question": "What jumps?", "evidence_quote": "brown fox jumps over"},
            {**base, "question": "Who is lazy?", "correct_index": 1, "evidence_quote": "the lazy dog"},
        ]

    monkeypatch.setattr(llm_service, "generate_listening_questions", fake)
    headers, user_id = login(listening_client)
    podcast_id, _ = asyncio.run(_seed_podcast(user_id))
    created = listening_client.post(
        f"/api/listening/podcasts/{podcast_id}/comprehension", headers=headers, json={}
    ).json()
    attempt_id = created["attempt_id"]

    # Số đáp án không khớp số câu -> 400, chưa chấm.
    bad = listening_client.post(f"/api/listening/quizzes/{attempt_id}/submit", headers=headers, json={"picks": [0]})
    assert bad.status_code == 400

    # Câu 1 đúng, câu 2 chọn sai (0 thay vì 1).
    result = listening_client.post(
        f"/api/listening/quizzes/{attempt_id}/submit", headers=headers, json={"picks": [0, 0]}
    ).json()
    assert (result["correct_count"], result["total"], result["score"]) == (1, 2, 50.0)
    assert result["correct"] == [True, False]

    # Nộp lại không ghi trùng lỗi và trả đúng kết quả cũ.
    again = listening_client.post(
        f"/api/listening/quizzes/{attempt_id}/submit", headers=headers, json={"picks": [1, 1]}
    ).json()
    assert again["correct_count"] == 1
    errors = listening_client.get("/api/adaptive/errors", headers=headers).json()
    items = errors["items"] if isinstance(errors, dict) else errors
    assert len([e for e in items if e["error_type"] == "listening_comprehension"]) == 1

    history = listening_client.get("/api/listening/quizzes", headers=headers).json()
    assert [(h["id"], h["score"]) for h in history] == [(attempt_id, 50.0)]


def test_trap_note_never_shows_option_numbers(listening_client, monkeypatch) -> None:
    async def fake(transcript: str, count: int) -> list[dict]:
        return [{
            "question": "What jumps?", "options": ["fox", "dog", "cat", "cow"], "correct_index": 0,
            "evidence_quote": "brown fox jumps over",
            "trap_note": "A listener might pick option 2 because dog is heard, not Option 4.",
        }]

    monkeypatch.setattr(llm_service, "generate_listening_questions", fake)
    headers, user_id = login(listening_client)
    podcast_id, _ = asyncio.run(_seed_podcast(user_id))
    note = listening_client.post(
        f"/api/listening/podcasts/{podcast_id}/comprehension", headers=headers, json={}
    ).json()["questions"][0]["trap_note"]
    assert note == 'A listener might pick "dog" because dog is heard, not "cow".'
