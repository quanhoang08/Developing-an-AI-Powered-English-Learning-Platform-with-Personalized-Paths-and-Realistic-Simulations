from app.services.ielts_service import pronunciation_band, to_band


def test_band_rounding_and_clamp() -> None:
    assert to_band(6.7) == 6.5
    assert to_band(6.25) == 6.5  # IELTS làm tròn .25 lên
    assert to_band(6.2) == 6.0
    assert to_band(70) == 9.0
    assert to_band(-1) == 0.0
    assert to_band("x") == 0.0
    assert pronunciation_band([]) is None
    assert pronunciation_band([80, 90]) == 7.5


from app.services import llm_service  # noqa: E402
from tests.test_listening_dictation_integration import listening_client, login  # noqa: E402,F401


def test_estimate_is_saved_and_compared_with_previous(listening_client, monkeypatch) -> None:
    scores = iter([5.0, 6.0])

    async def fake(answers: list[dict]) -> dict:
        band = next(scores)
        return {"fluency_coherence": band, "lexical_resource": band, "grammatical_range": band, "feedback_vi": "ok"}

    monkeypatch.setattr(llm_service, "estimate_ielts_band", fake)
    headers, _ = login(listening_client)
    body = {
        "topic": "travel",
        "answers": [{"part": 1, "question": "q", "transcript": "a b c", "pronunciation_score": 90, "words_per_minute": 120}],
    }
    first = listening_client.post("/api/speaking/ielts/estimate", headers=headers, json=body).json()
    second = listening_client.post("/api/speaking/ielts/estimate", headers=headers, json=body).json()
    assert first["previous_overall"] is None
    assert second["previous_overall"] == first["overall"]
    assert second["overall"] > first["overall"]

    history = listening_client.get("/api/speaking/ielts/attempts", headers=headers).json()
    assert [item["overall"] for item in history] == [second["overall"], first["overall"]]
    assert history[0]["topic"] == "travel" and history[0]["words_per_minute"] == 120


def test_pronunciation_cannot_lift_overall_more_than_one_band() -> None:
    from app.services.ielts_service import overall_band

    # Lạc đề (nội dung 0-2.5) nhưng phát âm 8.5: trước đây ra 3.0, giờ tối đa trung bình nội dung + 1.
    assert overall_band([2.5, 0.0, 0.0], 8.5) == 2.0
    # Bài cân bằng không bị ảnh hưởng.
    assert overall_band([6.0, 6.0, 6.0], 7.0) == 6.5
    assert overall_band([6.0, 6.0, 6.0], None) == 6.0
