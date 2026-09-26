# Unit test cho phần chấm Dictation THUẦN (word-diff + khoảng cách ngữ âm + gắn nhãn từ hiếm) —
# không đụng DB/HTTP, chạy nhanh, không phụ thuộc Postgres/Docker. So sánh với
# test_listening_dictation_integration.py (test đầy đủ qua API thật + DB thật).
from app.utils.dictation_grading import classify_error_type, diff_dictation, tokenize_submission
from app.utils.word_frequency import is_proper_noun, is_rare_word, tag_reference_words


def _errors_by_type(errors: list[dict], error_kind: str) -> list[dict]:
    return [error for error in errors if error["type"] == error_kind]


# ==================== word_frequency ====================


def test_is_rare_word_true_for_technical_term_false_for_common_word() -> None:
    assert is_rare_word("mitochondria") is True
    assert is_rare_word("hello") is False


def test_is_proper_noun_only_when_capitalized_and_not_sentence_start() -> None:
    assert is_proper_noun("Paris", is_sentence_start=False) is True
    assert is_proper_noun("The", is_sentence_start=True) is False
    assert is_proper_noun("the", is_sentence_start=False) is False


def test_tag_reference_words_marks_rare_and_proper_words() -> None:
    words = ["The", "mitochondria", "is", "in", "Paris"]
    tags = tag_reference_words(words, sentence_start_indices={0})
    assert tags[0] == {"word": "The", "is_rare_or_proper": False}
    assert tags[1]["is_rare_or_proper"] is True  # từ hiếm
    assert tags[4]["is_rare_or_proper"] is True  # tên riêng, không ở đầu câu


# ==================== classify_error_type ====================


def test_classify_missing_rare_word_as_vocabulary() -> None:
    assert classify_error_type("mitochondria", None, is_rare_or_proper=True) == "vocabulary"


def test_classify_missing_common_word_as_listening_comprehension() -> None:
    assert classify_error_type("hello", None, is_rare_or_proper=False) == "listening_comprehension"


def test_classify_wrong_common_word_phonetically_close_as_spelling() -> None:
    # "great" nghe/gõ nhầm thành "grate" — cùng mã Metaphone, từ thông dụng.
    assert classify_error_type("great", "grate", is_rare_or_proper=False) == "spelling"


def test_classify_wrong_rare_word_phonetically_close_as_vocabulary() -> None:
    # "mitochondria" gõ thành "mitocondria" — lệch 1 ký tự trên mã Metaphone, từ hiếm.
    assert classify_error_type("mitochondria", "mitocondria", is_rare_or_proper=True) == "vocabulary"


def test_classify_wrong_word_phonetically_far_as_listening_comprehension() -> None:
    # "hello" nghe nhầm hẳn thành "banana" — không liên quan gì về ngữ âm.
    assert classify_error_type("hello", "banana", is_rare_or_proper=False) == "listening_comprehension"


# ==================== tokenize_submission (contraction handling, mục 3.4) ====================


def test_tokenize_collapses_expanded_form_to_contracted() -> None:
    assert tokenize_submission("I do not like it") == ["i", "don't", "like", "it"]


def test_tokenize_lowercases_and_strips_punctuation() -> None:
    assert tokenize_submission("Hello, World!") == ["hello", "world"]


# ==================== diff_dictation (end-to-end thuần) ====================


def test_perfect_match_has_no_errors_and_full_score() -> None:
    reference = ["The", "quick", "brown", "fox"]
    tags = tag_reference_words(reference, {0})
    errors, score = diff_dictation(reference, tags, "The quick brown fox")
    assert errors == []
    assert score == 100.0


def test_missing_word_recorded_with_correct_position_and_error_type() -> None:
    reference = ["The", "mitochondria", "is", "small"]
    tags = tag_reference_words(reference, {0})
    errors, score = diff_dictation(reference, tags, "The is small")
    missing = _errors_by_type(errors, "missing")
    assert len(missing) == 1
    assert missing[0]["word"] == "mitochondria"
    assert missing[0]["position"] == 1
    assert missing[0]["error_type"] == "vocabulary"  # từ hiếm bị bỏ trống
    assert score == 75.0  # 3/4 từ đúng


def test_extra_word_has_no_error_type_and_does_not_affect_correct_count() -> None:
    reference = ["Hello", "world"]
    tags = tag_reference_words(reference, {0})
    errors, score = diff_dictation(reference, tags, "Hello there world")
    extra = _errors_by_type(errors, "extra")
    assert len(extra) == 1
    assert extra[0]["word"] == "there"
    assert extra[0]["error_type"] is None
    assert score == 100.0  # cả 2 từ gốc vẫn khớp đúng, "extra" không kéo điểm


def test_wrong_word_replace_classified_by_phonetic_distance() -> None:
    reference = ["I", "was", "very", "hungry"]
    tags = tag_reference_words(reference, {0})
    errors, score = diff_dictation(reference, tags, "I was very banana")
    wrong = _errors_by_type(errors, "wrong")
    assert len(wrong) == 1
    assert wrong[0]["word"] == "hungry"
    assert wrong[0]["position"] == 3
    assert wrong[0]["error_type"] == "listening_comprehension"
    assert score == 75.0


def test_contraction_equivalence_between_reference_and_submission() -> None:
    # Reference lưu "don't" (1 token, đúng dạng lời nói tự nhiên) — người học gõ "do not".
    reference = ["I", "don't", "like", "it"]
    tags = tag_reference_words(reference, {0})
    errors, score = diff_dictation(reference, tags, "I do not like it")
    assert errors == []
    assert score == 100.0


def test_case_and_punctuation_differences_are_not_errors() -> None:
    reference = ["Hello", "world"]
    tags = tag_reference_words(reference, {0})
    errors, score = diff_dictation(reference, tags, "hello, world.")
    assert errors == []
    assert score == 100.0


def test_blank_submission_marks_every_reference_word_as_missing() -> None:
    reference = ["One", "two", "three"]
    tags = tag_reference_words(reference, {0})
    errors, score = diff_dictation(reference, tags, "")
    assert len(_errors_by_type(errors, "missing")) == 3
    assert score == 0.0


def test_resubmitting_same_input_is_deterministic() -> None:
    reference = ["The", "cat", "sat"]
    tags = tag_reference_words(reference, {0})
    first_errors, first_score = diff_dictation(reference, tags, "The dog sat")
    second_errors, second_score = diff_dictation(reference, tags, "The dog sat")
    assert first_errors == second_errors
    assert first_score == second_score
