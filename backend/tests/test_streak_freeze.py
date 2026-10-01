from datetime import date

from app.services.gamification_service import missed_days, visible_streak

TODAY = date(2026, 10, 1)


def test_missed_days_counts_only_full_missed_days() -> None:
    assert missed_days(5, date(2026, 9, 30), TODAY) == 0  # học hôm qua
    assert missed_days(5, date(2026, 9, 29), TODAY) == 1  # bỏ lỡ 30/9
    assert missed_days(5, TODAY, TODAY) == 0
    assert missed_days(0, date(2026, 9, 20), TODAY) == 0  # chưa có chuỗi thì không có gì để lấp


def test_freeze_keeps_streak_visible_only_when_it_covers_missed_days() -> None:
    last = date(2026, 9, 29)  # bỏ lỡ đúng 1 ngày
    assert visible_streak(7, last, TODAY) == 0
    assert visible_streak(7, last, TODAY, freezes=1) == 7
    assert visible_streak(7, date(2026, 9, 27), TODAY, freezes=1) == 0  # bỏ lỡ 3 ngày > 1 freeze
