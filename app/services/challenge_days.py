from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


MONTHS_RU = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def challenge_day_for(
    moment: datetime,
    tz_name: str = "Europe/Moscow",
    close_time: time = time(1, 0),
) -> date:
    local_moment = moment.astimezone(ZoneInfo(tz_name))
    if local_moment.timetz().replace(tzinfo=None) < close_time:
        return local_moment.date() - timedelta(days=1)
    return local_moment.date()


def challenge_day_window(
    day: date,
    tz_name: str = "Europe/Moscow",
    close_time: time = time(1, 0),
) -> tuple[datetime, datetime]:
    timezone = ZoneInfo(tz_name)
    starts_at = datetime.combine(day, close_time, tzinfo=timezone)
    return starts_at, starts_at + timedelta(days=1)


def next_challenge_start(
    moment: datetime,
    tz_name: str = "Europe/Moscow",
    close_time: time = time(1, 0),
) -> datetime:
    next_day = challenge_day_for(moment, tz_name, close_time) + timedelta(days=1)
    starts_at, _ = challenge_day_window(next_day, tz_name, close_time)
    return starts_at


def render_daily_list(day: date, names: Sequence[str]) -> str:
    title = f"Список за {day.day} {MONTHS_RU[day.month]}"
    if not names:
        return f"{title}\n\nВ общем списке за сегодня пока никого нет.\nЖду видео в этой теме до 01:00 МСК."

    rendered_names = "\n".join(f"• {name}" for name in names)
    return f"{title}\n\nСегодня отчёт приняли от:\n{rendered_names}\n\nЖду видео в этой теме до 01:00 МСК."
