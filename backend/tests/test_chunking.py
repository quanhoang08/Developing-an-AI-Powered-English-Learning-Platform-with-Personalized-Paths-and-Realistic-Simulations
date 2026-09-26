"""Unit test cho các chiến lược chia chunk RAG (không cần DB/Ollama/mạng)."""
import pytest

from app.utils.chunking import (
    chunk_document,
    fixed_chunks,
    paragraph_chunks,
    sentence_chunks,
    split_sentences,
)

EN = "Spaced repetition schedules reviews at growing intervals. It fights the forgetting curve. Dr. Smith proved it, e.g. in 1885."
VI = "Lặp lại ngắt quãng lên lịch ôn tập theo khoảng cách tăng dần. Nó chống lại đường cong quên lãng. Đây là phương pháp hiệu quả."


def test_split_sentences_english_keeps_abbreviations() -> None:
    sentences = split_sentences(EN)
    assert len(sentences) == 3
    assert sentences[2].startswith("Dr. Smith") and "e.g." in sentences[2]


def test_split_sentences_vietnamese_uppercase_and_lowercase_accents() -> None:
    sentences = split_sentences(VI)
    assert len(sentences) == 3
    assert sentences[1].startswith("Nó ") and sentences[2].startswith("Đây")
    # Chữ thường có dấu sau dấu chấm không được coi là đầu câu mới.
    assert len(split_sentences("Xong rồi. ăn cơm thôi.")) == 1


def test_fixed_chunks_cut_by_word_count_only() -> None:
    chunks = fixed_chunks(" ".join(str(i) for i in range(25)), 10)
    assert [len(c.split()) for c in chunks] == [10, 10, 5]


def test_paragraph_chunks_never_split_a_paragraph_and_respect_size() -> None:
    text = "one two three\nfour five six\nseven eight nine ten eleven"
    chunks = paragraph_chunks(text, 6)
    assert chunks == ["one two three\nfour five six", "seven eight nine ten eleven"]


def test_paragraph_chunks_hard_split_oversized_paragraph() -> None:
    chunks = paragraph_chunks(" ".join(["w"] * 25), 10)
    assert [len(c.split()) for c in chunks] == [10, 10, 5]


def test_sentence_chunks_keep_whole_sentences_with_overlap() -> None:
    text = " ".join(f"Sentence number {i} has exactly seven words here." for i in range(10))
    chunks = sentence_chunks(text, max_words=25, overlap_sentences=1)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.split()) <= 25
        assert chunk.endswith(".")  # không cắt ngang câu
    # Câu cuối của chunk trước xuất hiện lại ở đầu chunk sau.
    last_sentence_of_first = split_sentences(chunks[0])[-1]
    assert chunks[1].startswith(last_sentence_of_first)


def test_sentence_chunks_without_overlap_do_not_repeat() -> None:
    text = " ".join(f"Sentence number {i} has exactly seven words here." for i in range(10))
    chunks = sentence_chunks(text, max_words=25, overlap_sentences=0)
    assert sum(len(c.split()) for c in chunks) == len(text.split())


def test_sentence_chunks_split_single_overlong_sentence() -> None:
    chunks = sentence_chunks(" ".join(["word"] * 60) + ".", max_words=20)
    assert all(len(c.split()) <= 20 for c in chunks)
    assert sum(len(c.split()) for c in chunks) >= 60


def test_all_strategies_preserve_all_content_words() -> None:
    text = f"{EN}\n{VI}"
    original = set(text.split())
    for strategy in ("fixed", "paragraph", "sentence"):
        rebuilt = set(" ".join(chunk_document(text, strategy, max_words=12)).split())
        assert original <= rebuilt, strategy


def test_empty_text_and_unknown_strategy() -> None:
    assert chunk_document("", "sentence") == []
    assert chunk_document("   \n  ", "paragraph") == []
    with pytest.raises(ValueError):
        chunk_document("x", "semantic")
