from app.utils.subtitles import clip_cues, merge_cues, parse_srt

SRT = (
    "﻿1\r\n00:00:01,000 --> 00:00:03,000\r\n<i>Don't worry.</i> It's a piece of\r\n\r\n"
    "2\r\n00:00:03,200 --> 00:00:04,500\r\ncake.\r\n\r\n"
    "3\r\n00:00:05,000 --> 00:00:06,000\r\n[door slams]\r\n\r\n"
    "4\r\n00:01:00,000 --> 00:01:02,500\r\n- Are you coming?\r\n\r\n"
    "5\r\n00:01:10,000 --> 00:01:12,000\r\n{\\an8}♪ la la ♪\r\n"
)


def test_parse_cleans_markup_and_skips_non_speech() -> None:
    cues = parse_srt(SRT.lstrip("﻿"))
    assert cues == [
        (1000, 3000, "Don't worry. It's a piece of"),
        (3200, 4500, "cake."),
        (60000, 62500, "Are you coming?"),
    ]


def test_merge_joins_idiom_split_across_cues_but_not_finished_sentences() -> None:
    merged = merge_cues(parse_srt(SRT.lstrip("﻿")))
    assert merged[0] == (1000, 4500, "Don't worry. It's a piece of cake.")
    # Cue đã kết thúc câu / cách xa thì giữ riêng.
    assert merged[1] == (60000, 62500, "Are you coming?")


def test_merge_respects_gap_and_sentence_end() -> None:
    cues = [(0, 1000, "So we could"), (5000, 6000, "go now."), (6100, 7000, "Okay.")]
    assert merge_cues(cues) == cues  # cách nhau 4s -> không gộp; "go now." đã hết câu


def test_clip_shifts_times_and_drops_cues_outside_range() -> None:
    cues = [(1000, 2000, "a."), (60000, 62500, "b."), (200000, 201000, "c.")]
    assert clip_cues(cues, 30000, 120000) == [(30000, 32500, "b.")]
    assert clip_cues(cues, 30000, None) == [(30000, 32500, "b."), (170000, 171000, "c.")]
