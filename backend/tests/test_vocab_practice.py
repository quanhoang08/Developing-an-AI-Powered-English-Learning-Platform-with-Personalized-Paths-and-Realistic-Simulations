import asyncio

import pytest

from app.services import llm_service
from app.services.vocab_practice_service import find_missing_terms


def test_find_missing_terms_matches_inflections_case_insensitively() -> None:
    content = "She was Running late, so the deadline felt unavoidable."
    assert find_missing_terms(content, ["run", "deadline", "frugal"]) == ["frugal"]


def _challenge(monkeypatch: pytest.MonkeyPatch, payload: dict) -> dict:
    monkeypatch.setattr(llm_service, "_generate_json", lambda prompt, schema: payload)
    return asyncio.run(llm_service.generate_guess_challenge("frugal", "careful with money"))


def test_guess_challenge_filters_term_and_duplicates_from_distractors(monkeypatch) -> None:
    result = _challenge(
        monkeypatch,
        {
            "challenge_sentence": "He is very _____ with his money.",
            "distractors": ["Frugal", "generous", "generous", "lazy", "noisy", "tall"],
        },
    )
    assert result["distractors"] == ["generous", "lazy", "noisy"]


def test_guess_challenge_rejects_sentence_without_blank(monkeypatch) -> None:
    with pytest.raises(llm_service.AIServiceError):
        _challenge(
            monkeypatch,
            {"challenge_sentence": "He is frugal.", "distractors": ["a", "b", "c"]},
        )


def test_guess_challenge_rejects_too_few_distractors(monkeypatch) -> None:
    with pytest.raises(llm_service.AIServiceError):
        _challenge(
            monkeypatch,
            {"challenge_sentence": "He is _____.", "distractors": ["frugal", "lazy", "noisy"]},
        )


def _spy_ollama(monkeypatch: pytest.MonkeyPatch, missing_models: set[str]) -> list[str]:
    import json

    import ollama

    used: list[str] = []

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def chat(self, model, **kwargs):
            used.append(model)
            if model in missing_models:
                raise ollama.ResponseError("not found", 404)
            payload = {"corrected_sentence": "x", "grammar_ok": True, "meaning_fits": True, "feedback_vi": "ok"}
            return type("R", (), {"message": type("M", (), {"content": json.dumps(payload)})()})()

    monkeypatch.setattr(ollama, "Client", FakeClient)
    return used


def test_judge_uses_judge_model_with_low_temperature(monkeypatch) -> None:
    from app.core.config import get_settings

    used = _spy_ollama(monkeypatch, set())
    asyncio.run(llm_service.judge_vocab_sentence("mitigate", "Trees mitigate harm."))
    assert used == [get_settings().ollama_judge_model_name]


def test_judge_falls_back_to_default_model_when_judge_model_missing(monkeypatch) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    used = _spy_ollama(monkeypatch, {settings.ollama_judge_model_name})
    asyncio.run(llm_service.judge_vocab_sentence("mitigate", "Trees mitigate harm."))
    assert used == [settings.ollama_judge_model_name, settings.ollama_model_name]
