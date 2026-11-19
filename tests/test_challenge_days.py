from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.services.challenge_days import (
    challenge_day_for,
    challenge_day_window,
    next_challenge_start,
    render_daily_list,
)


MSK = ZoneInfo("Europe/Moscow")


def test_video_before_1am_belongs_to_previous_calendar_day():
    assert challenge_day_for(datetime(2026, 10, 4, 0, 59, tzinfo=MSK)) == date(2026, 10, 3)


def test_video_at_1am_belongs_to_current_calendar_day():
    assert challenge_day_for(datetime(2026, 10, 4, 1, 0, tzinfo=MSK)) == date(2026, 10, 4)


def test_challenge_day_window_runs_1am_to_next_1am():
    starts_at, ends_at = challenge_day_window(date(2026, 10, 4))

    assert starts_at == datetime(2026, 10, 4, 1, 0, tzinfo=MSK)
    assert ends_at == datetime(2026, 10, 5, 1, 0, tzinfo=MSK)


def test_next_challenge_starts_on_next_challenge_day():
    assert next_challenge_start(datetime(2026, 11, 7, 12, 0, tzinfo=MSK)) == datetime(
        2026, 11, 8, 1, 0, tzinfo=MSK
    )


def test_payment_before_1am_starts_at_upcoming_1am():
    assert next_challenge_start(datetime(2026, 11, 7, 0, 15, tzinfo=MSK)) == datetime(
        2026, 11, 7, 1, 0, tzinfo=MSK
    )


def test_render_daily_list_with_names():
    text = render_daily_list(date(2026, 10, 4), ["Участник А.", "Участник Б."])

    assert "Список за 4 октября" in text
    assert "Участник А." in text
    assert "Участник Б." in text


def test_render_daily_list_empty():
    text = render_daily_list(date(2026, 10, 4), [])

    assert "пока никого нет" in text
    assert "Жду видео" in text
