"""Unit test cho tra từ Vietnamese-CEFR: không cần DB, Ollama hay mạng (mọi phụ thuộc đều bị thay bằng bản giả)."""
import asyncio

import pytest

from app.services import llm_service, reading_service

BANK = [
    {"part_of_speech": "noun", "definition": "An institution where one can borrow money.", "example": ""},
    {"part_of_speech": "verb", "definition": "To rely on; to place trust in.", "example": "I am banking on you."},
    {"part_of_speech": "noun", "definition": "The land alongside a river or lake.", "example": "We sat on the bank."},
]


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    reading_service._LOOKUP_CACHE.clear()


def test_is_vietnamese_rejects_plain_english() -> None:
    assert reading_service._is_vietnamese("bờ sông")
    assert reading_service._is_vietnamese("ĐIỀU HÀNH")
    assert not reading_service._is_vietnamese("Rely on; trust in")
    assert not reading_service._is_vietnamese("")


def test_merge_matches_by_index_not_position_and_puts_context_sense_first() -> None:
    # Model đảo thứ tự items: ghép theo "index" thì nghĩa vẫn gắn đúng định nghĩa.
    raw = {
        "best_index": 2,
        "items": [
            {"index": 2, "level": "A2", "meaning_vi": "bờ sông"},
            {"index": 0, "level": "B1", "meaning_vi": "ngân hàng"},
            {"index": 1, "level": "C1", "meaning_vi": "tin cậy vào"},
        ],
    }
    senses = reading_service._merge_translated_senses(BANK, raw)
    assert [s["meaning_vi"] for s in senses] == ["bờ sông", "ngân hàng", "tin cậy vào"]
    assert senses[0]["part_of_speech"] == "noun" and senses[0]["example_en"] == "We sat on the bank."
    assert senses[2]["part_of_speech"] == "verb"


def test_merge_orders_remaining_senses_by_cefr_and_drops_non_vietnamese() -> None:
    raw = {
        "best_index": 0,
        "items": [
            {"index": 0, "level": "B2", "meaning_vi": "ngân hàng"},
            {"index": 1, "level": "A2", "meaning_vi": "Rely on"},  # tiếng Anh → bị loại
            {"index": 2, "level": "A1", "meaning_vi": "bờ sông"},
        ],
    }
    senses = reading_service._merge_translated_senses(BANK, raw)
    assert [s["meaning_vi"] for s in senses] == ["ngân hàng", "bờ sông"]


def test_lookup_term_uses_dictionary_then_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"translate": 0}

    async def fake_dictionary(term: str) -> list[dict]:
        return BANK

    async def fake_translate(term: str, context: str, definitions: list[str]) -> dict:
        calls["translate"] += 1
        return {
            "ipa": "/bæŋk/",
            "best_index": 2,
            "items": [
                {"index": 0, "level": "A2", "meaning_vi": "ngân hàng"},
                {"index": 1, "level": "C1", "meaning_vi": "tin cậy vào"},
                {"index": 2, "level": "B1", "meaning_vi": "bờ sông"},
            ],
            "synonyms": [],
            "antonyms": [],
        }

    monkeypatch.setattr(reading_service, "_fetch_dictionary_candidates", fake_dictionary)
    monkeypatch.setattr(llm_service, "translate_word_senses", fake_translate)

    first = asyncio.run(reading_service.lookup_term("bank", "We sat on the bank."))
    second = asyncio.run(reading_service.lookup_term("bank", "We sat on the bank."))
    assert first["definition"] == "bờ sông"
    assert first["ipa"] == "/bæŋk/"
    assert first is second
    assert calls["translate"] == 1  # lần hai lấy từ cache, không gọi lại Ollama


def test_lookup_term_falls_back_to_single_sense_when_dictionary_down(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_dictionary(term: str) -> list[dict]:
        return []

    async def fake_single(term: str, context: str) -> dict:
        return {
            "ipa": "/rʌn/",
            "senses": [{"part_of_speech": "verb", "level": "B1", "meaning_vi": "điều hành", "example_en": "He runs a shop."}],
            "synonyms": ["manage"],
            "antonyms": [],
        }

    monkeypatch.setattr(reading_service, "_fetch_dictionary_candidates", no_dictionary)
    monkeypatch.setattr(llm_service, "lookup_word_vi", fake_single)
    result = asyncio.run(reading_service.lookup_term("run", "He runs a shop."))
    assert result["definition"] == "điều hành"
    assert len(result["senses"]) == 1


def test_lookup_term_propagates_ai_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_dictionary(term: str) -> list[dict]:
        return []

    async def broken(term: str, context: str) -> dict:
        raise llm_service.AIServiceError("ollama down")

    monkeypatch.setattr(reading_service, "_fetch_dictionary_candidates", no_dictionary)
    monkeypatch.setattr(llm_service, "lookup_word_vi", broken)
    with pytest.raises(llm_service.AIServiceError):
        asyncio.run(reading_service.lookup_term("run", "He runs a shop."))
