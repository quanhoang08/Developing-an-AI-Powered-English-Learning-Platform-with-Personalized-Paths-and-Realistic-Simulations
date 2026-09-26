import pytest

from app.services import llm_service
from app.services.rearrange_service import (
    build_grammar_blocks,
    grade_order,
    paragraph_blocks,
    shuffle_order,
    split_sentences,
)


def test_split_sentences_normalizes_whitespace() -> None:
    assert split_sentences("First one.  Second?\nThird! Fourth") == ["First one.", "Second?", "Third!", "Fourth"]


def test_paragraph_blocks_caps_at_six_and_needs_three() -> None:
    text = " ".join(f"Sentence number {i} is here." for i in range(9))
    assert len(paragraph_blocks(text)) == 6
    assert paragraph_blocks("Only one. Only two.") is None


def test_paragraph_blocks_rejects_overlong_sentence() -> None:
    long_sentence = " ".join(["word"] * 61) + "."
    assert paragraph_blocks(f"Short one. {long_sentence} Short two.") is None


def test_grade_order_partial_credit_matches_spec_rd_032() -> None:
    # RD-032: 5 khối, đặt đúng 3/5 vị trí → 0.60.
    correct = ["a", "b", "c", "d", "e"]
    score, best = grade_order(["a", "b", "c", "e", "d"], [correct])
    assert score == 0.6
    assert best == correct


def test_grade_order_perfect_and_zero() -> None:
    correct = ["a", "b", "c"]
    assert grade_order(correct, [correct])[0] == 1.0
    assert grade_order(["b", "c", "a"], [correct])[0] == 0.0


def test_grade_order_open_form_accepts_alternative_order() -> None:
    primary = ["subj", "verb", "adverbial"]
    alternative = ["adverbial", "subj", "verb"]
    score, best = grade_order(alternative, [primary, alternative])
    assert score == 1.0
    assert best == alternative


def test_shuffle_order_never_returns_an_accepted_order() -> None:
    ids = ["a", "b", "c", "d"]
    for _ in range(50):
        assert shuffle_order(ids, [ids]) != ids


def test_build_grammar_blocks_keeps_only_valid_alternatives() -> None:
    result = {
        "sentence": "Yesterday she walked to school.",
        "chunks": ["Yesterday", "she walked", "to school."],
        "alternative_orders": [[1, 2, 0], [0, 1, 2], [0, 0, 1], [2, 0], [1, 2, 0]],
    }
    chunks, alternatives = build_grammar_blocks(result, None)
    assert chunks == ["Yesterday", "she walked", "to school."]
    # Bỏ thứ tự trùng chuẩn, thứ tự lặp chỉ số, thiếu chỉ số và bản trùng lặp.
    assert alternatives == [[1, 2, 0]]


def test_build_grammar_blocks_rejects_chunks_that_change_the_sentence() -> None:
    result = {"sentence": "She walked to school.", "chunks": ["She", "walked", "home."], "alternative_orders": []}
    with pytest.raises(llm_service.AIServiceError):
        build_grammar_blocks(result, None)


def test_build_grammar_blocks_checks_against_given_source_sentence() -> None:
    result = {"sentence": "ignored", "chunks": ["I", "like", "tea."], "alternative_orders": []}
    assert build_grammar_blocks(result, "I like tea.")[0] == ["I", "like", "tea."]
    with pytest.raises(llm_service.AIServiceError):
        build_grammar_blocks(result, "I like coffee.")


def test_build_grammar_blocks_rejects_too_few_chunks() -> None:
    result = {"sentence": "Hi there.", "chunks": ["Hi", "there."], "alternative_orders": []}
    with pytest.raises(llm_service.AIServiceError):
        build_grammar_blocks(result, None)


def test_build_grammar_blocks_ignores_punctuation_and_case_like_real_model_output() -> None:
    # Output thật của qwen2.5-7b: bỏ dấu chấm cuối câu, hoặc tách dấu chấm thành khối riêng.
    no_period = {"sentence": "I usually go to the park on weekends.", "chunks": ["I usually go", "to the park", "on weekends"], "alternative_orders": []}
    assert len(build_grammar_blocks(no_period, None)[0]) == 3
    split_period = {"sentence": "I usually go for a walk in the morning.", "chunks": ["I usually go", "for a walk", "in the morning", "."], "alternative_orders": []}
    assert len(build_grammar_blocks(split_period, None)[0]) == 4
    lowercase = {"sentence": "She often reads books.", "chunks": ["she often", "reads", "books"], "alternative_orders": []}
    assert build_grammar_blocks(lowercase, None)[0] == ["she often", "reads", "books"]


def test_build_grammar_blocks_still_rejects_missing_words_after_loosening() -> None:
    result = {"sentence": "She often reads books in the library.", "chunks": ["She often", "reads books", "the library"], "alternative_orders": []}
    with pytest.raises(llm_service.AIServiceError) as info:
        build_grammar_blocks(result, None)
    assert info.value.code == "ai_bad_output"
