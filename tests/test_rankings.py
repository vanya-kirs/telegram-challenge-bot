import pytest

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.db.models import ChallengeDay, Participant, ParticipantStatus, Report
from app.services.challenge_days import challenge_day_window
from app.services.rankings import build_completion_ranking, completion_percent, participation_days


@pytest.mark.parametrize(
    ("reports", "days", "expected"),
    [(0, 0, 0.0), (0, 3, 0.0), (2, 4, 50.0), (3, 3, 100.0)],
)
def test_completion_percent(reports, days, expected):
    assert completion_percent(reports, days) == expected


def test_participation_days_uses_moscow_challenge_day_for_utc_timestamp():
    participant = Participant(
        telegram_user_id=123,
        display_name="Участник А.",
        status=ParticipantStatus.ACTIVE,
        challenge_started_at=datetime(2026, 11, 7, 22, 0, tzinfo=ZoneInfo("UTC")),
    )

    assert participation_days(participant, date(2026, 11, 8)) == 1


@pytest.mark.asyncio
async def test_completion_ranking_uses_only_recorded_reports_and_misses(db_session):
    starts_at, ends_at = challenge_day_window(date(2026, 10, 2))
    participant = Participant(
        telegram_user_id=123,
        display_name="Участник А.",
        status=ParticipantStatus.ACTIVE,
        challenge_started_at=datetime(2026, 10, 1, 12, 0, tzinfo=ZoneInfo("Europe/Moscow")),
    )
    challenge_day = ChallengeDay(day=date(2026, 10, 2), starts_at=starts_at, ends_at=ends_at)
    db_session.add_all([participant, challenge_day])
    await db_session.flush()
    db_session.add(
        Report(
            participant_id=participant.id,
            challenge_day_id=challenge_day.id,
            telegram_message_id=1,
            telegram_chat_id=-100,
            telegram_thread_id=7,
            file_id="file",
            file_unique_id="unique",
            submitted_at=datetime(2026, 10, 2, 12, 0, tzinfo=ZoneInfo("Europe/Moscow")),
        )
    )
    await db_session.flush()

    ranking = await build_completion_ranking(db_session, today=date(2026, 10, 4))

    assert ranking[0].reports_count == 1
    assert ranking[0].participation_days == 1
    assert ranking[0].completion_percent == 100.0
