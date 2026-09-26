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
