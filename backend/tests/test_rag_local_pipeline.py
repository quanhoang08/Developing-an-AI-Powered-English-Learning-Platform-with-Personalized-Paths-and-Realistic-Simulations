"""Test cho pipeline RAG chạy local: chọn cột embedding theo provider, model Modelfile + đường lùi, và các
hàm chấm điểm của thực nghiệm. Không cần DB, Ollama hay mạng (mọi lời gọi Ollama bị thay bằng bản giả)."""
import sys
from pathlib import Path
from types import SimpleNamespace

import ollama
import pytest

from app.services import llm_service, rag_service

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "experiments"))
import lib  # noqa: E402
import run_generation as gen  # noqa: E402


def fake_settings(**overrides) -> SimpleNamespace:
    values = {
        "embedding_provider": "ollama",
        "ollama_base_url": "http://localhost:11434",
        "ollama_rag_model_name": "lumina-rag-qwen",
        "ollama_model_name": "qwen2.5:7b-instruct-q4_K_M",
        "ollama_temperature": 0.7,
        "llm_provider": "ollama",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeClient:
    """Thay ollama.Client: ghi lại lời gọi chat và có thể giả lập model chưa được tạo (404)."""

    calls: list[dict] = []
    missing_models: set[str] = set()

    def __init__(self, host: str | None = None, **_: object) -> None:
        pass

    def chat(self, model: str, messages: list[dict], **kwargs: object) -> SimpleNamespace:
        FakeClient.calls.append({"model": model, "prompt": messages[0]["content"]})
        if model in FakeClient.missing_models:
            raise ollama.ResponseError(f"model '{model}' not found", 404)
        return SimpleNamespace(message=SimpleNamespace(content=f"  answer from {model}  "))


@pytest.fixture(autouse=True)
def reset_fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeClient.calls, FakeClient.missing_models = [], set()
    monkeypatch.setattr(llm_service.ollama, "Client", FakeClient)
    monkeypatch.setattr(llm_service, "get_settings", lambda: fake_settings())


def test_embedding_field_follows_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rag_service, "get_settings", lambda: fake_settings(embedding_provider="ollama"))
    assert rag_service.embedding_field() == "embedding_local"
    monkeypatch.setattr(rag_service, "get_settings", lambda: fake_settings(embedding_provider="gemini"))
    assert rag_service.embedding_field() == "embedding"


def test_rag_answer_uses_modelfile_model_with_numbered_excerpts() -> None:
    answer = llm_service._answer_with_rag_model(
        ["first chunk", "second chunk"], "What is X?", [{"role": "user", "content": "hi"}]
    )
    assert answer == "answer from lumina-rag-qwen"
    call = FakeClient.calls[0]
    assert call["model"] == "lumina-rag-qwen"
    assert "[1] first chunk" in call["prompt"] and "[2] second chunk" in call["prompt"]
    assert "QUESTION: What is X?" in call["prompt"] and "user: hi" in call["prompt"]
    assert call["prompt"].rstrip().endswith("ANSWER LANGUAGE: English")


def test_language_detection_decides_answer_language() -> None:
    from app.utils.language import is_vietnamese, language_name

    assert language_name("Khi nào dùng has thay vì have?") == "Vietnamese"
    assert language_name("Give up nghĩa là gì?") == "Vietnamese"
    assert language_name("What does 'run out of' mean?") == "English"
    assert not is_vietnamese("") and not is_vietnamese("12345 ???")
    # Prompt tiếng Việt phải yêu cầu trả lời tiếng Việt kể cả khi tài liệu là tiếng Anh.
    llm_service._answer_with_rag_model(["English excerpt"], "Câu này nghĩa là gì?", [])
    assert FakeClient.calls[-1]["prompt"].rstrip().endswith("ANSWER LANGUAGE: Vietnamese")


def test_rag_answer_falls_back_to_base_model_when_modelfile_missing() -> None:
    FakeClient.missing_models = {"lumina-rag-qwen"}
    answer = llm_service._answer_with_rag_model(["chunk"], "Q?", [])
    assert answer == "answer from qwen2.5:7b-instruct-q4_K_M"
    assert [c["model"] for c in FakeClient.calls] == ["lumina-rag-qwen", "qwen2.5:7b-instruct-q4_K_M"]
    # Model gốc không có SYSTEM prompt nên luật phải nằm trong user prompt.
    assert "Answer ONLY using the excerpts" in FakeClient.calls[1]["prompt"]


def test_rag_answer_other_ollama_errors_become_ai_service_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class Broken(FakeClient):
        def chat(self, model: str, messages: list[dict], **kwargs: object):
            raise ollama.ResponseError("server exploded", 500)

    monkeypatch.setattr(llm_service.ollama, "Client", Broken)
    with pytest.raises(llm_service.AIServiceError):
        llm_service._answer_with_rag_model(["c"], "Q?", [])


# ---------- hàm chấm điểm của thực nghiệm ----------

def test_refusal_detection_covers_both_languages() -> None:
    assert gen.is_refusal("Tài liệu không đề cập đến nội dung này. / The document does not cover this.")
    assert gen.is_refusal("The provided excerpts do not contain information about that.")
    assert gen.is_refusal("The document doesn't mention it.")
    assert not gen.is_refusal("The ease factor starts at 2.5 [1].")


def test_keywords_ok_needs_every_group_and_ignores_accents() -> None:
    groups = [["quay về", "returned"], ["vẫn", "still"]]
    assert gen.keywords_ok("Đã QUAY VE rồi, còn kia van ở đó", groups)
    assert not gen.keywords_ok("She returned home.", groups)


def test_answer_language_and_grounding_proxy() -> None:
    assert gen.answer_language("Hệ số dễ ban đầu là 2.5 theo tài liệu") == "vi"
    assert gen.answer_language("The ease factor starts at 2.5") == "en"
    assert gen.grounded_ratio("ebbinghaus described forgetting", "Hermann Ebbinghaus described the forgetting curve") == 1.0
    assert gen.grounded_ratio("astronauts discovered volcanoes", "The forgetting curve") == 0.0


# ---------- thư viện retrieval ----------

def test_bm25_ranks_the_lexically_matching_chunk_first() -> None:
    chunks = ["the leitner system uses five boxes", "sleep helps memory consolidation", "ease factor starts at 2.5"]
    scores = lib.BM25(chunks).scores("how many boxes in the leitner system")
    assert lib.rank_by(scores)[0] == 0


def test_bm25_handles_vietnamese_syllables() -> None:
    chunks = ["thì hiện tại hoàn thành dùng have hoặc has", "phrasal verb là cụm động từ"]
    assert lib.rank_by(lib.BM25(chunks).scores("cụm động từ là gì"))[0] == 1


def test_reciprocal_rank_fusion_prefers_items_ranked_high_by_both_lists() -> None:
    # Phần tử 1 có mặt ở CẢ hai bảng (hạng 2 và 1) nên thắng phần tử 7 chỉ đứng đầu 1 bảng.
    assert lib.reciprocal_rank_fusion([[7, 1, 2], [1, 3, 4]])[0] == 1
    assert lib.reciprocal_rank_fusion([[3, 0], [3, 1]])[0] == 3
    assert sorted(lib.reciprocal_rank_fusion([[0, 1], [2]])) == [0, 1, 2]  # gộp đủ mọi phần tử


def test_gold_rank_and_summary_metrics() -> None:
    chunks = ["alpha beta", "the ease  factor STARTS at 2.5", "gamma"]
    assert lib.gold_rank(chunks, "ease factor starts at 2.5") == 2
    assert lib.gold_rank(chunks, "missing phrase") is None
    summary = lib.summarize([1, 2, None, 5])
    assert summary["hit@1"] == 0.25 and summary["hit@3"] == 0.5 and summary["hit@5"] == 0.75
    assert summary["mrr@5"] == pytest.approx((1 + 0.5 + 0 + 0.2) / 4)
