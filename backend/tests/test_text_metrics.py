from app.utils.text_metrics import sentence_structures, speech_metrics


def test_sentence_structures_classify_types_and_features() -> None:
    text = (
        "I like tea. "
        "I like tea, but she prefers coffee. "
        "Although it was late, we kept working. "
        "The report, which was written by Tom, was long, and nobody read it. "
        "If you study, you will pass. "
        "Do you agree?"
    )
    result = sentence_structures(text)
    assert result["sentence_count"] == 6
    assert result["types"] == {"simple": 2, "compound": 1, "complex": 2, "compound_complex": 1}
    assert result["features"] == {"conditional": 1, "passive": 1, "relative_clause": 1, "question": 1}
    assert result["distinct_structures"] == 8


def test_sentence_structures_empty_text() -> None:
    assert sentence_structures("  ")["sentence_count"] == 0


def test_speech_metrics_counts_fillers_and_diversity() -> None:
    result = speech_metrics("Um, I think, you know, I think it is good")
    assert result["filler_count"] == 2
    assert result["lexical_diversity"] == 0.8  # 8 từ khác nhau / 10 từ
    assert speech_metrics("") == {"filler_count": 0, "lexical_diversity": 0.0}


def test_compound_without_comma_but_not_noun_coordination() -> None:
    result = sentence_structures(
        "I like tea but she likes coffee. "
        "It rained and the match was cancelled. "
        "I like tea and coffee. "
        "She is tired but happy."
    )
    assert result["types"] == {"simple": 2, "compound": 2, "complex": 0, "compound_complex": 0}


def test_compound_with_proper_name_subject() -> None:
    result = sentence_structures(
        "We waited at the station and Tom left early. "  # ghép: chủ ngữ mới là tên riêng
        "Tom and Mary went home. "  # chủ ngữ ghép: câu đơn
        "She met Tom and Mary yesterday."  # danh từ ghép: câu đơn
    )
    assert result["types"] == {"simple": 2, "compound": 1, "complex": 0, "compound_complex": 0}
