from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.participants import accept_rules, upsert_registered_participant
from app.services.reports import accept_video_report


MSK = ZoneInfo("Europe/Moscow")


@pytest.mark.asyncio
async def test_accepts_first_video_report(db_session):
    participant = await upsert_registered_participant(db_session, 123, None, "Участник А.")
    await accept_rules(db_session, participant, datetime(2026, 10, 4, 0, 30, tzinfo=MSK))

    decision = await accept_video_report(
        db_session,
        telegram_user_id=123,
        message_id=10,
        chat_id=-100,
        thread_id=7,
        file_id="file-id",
        file_unique_id="unique-1",
        submitted_at=datetime(2026, 10, 4, 1, 5, tzinfo=MSK),
        expected_thread_id=7,
    )

    assert decision.accepted is True


@pytest.mark.asyncio
async def test_rejects_duplicate_video_globally(db_session):
    first = await upsert_registered_participant(db_session, 123, None, "Участник А.")
    second = await upsert_registered_participant(db_session, 456, None, "Участник Б.")
    now = datetime(2026, 10, 4, 1, 5, tzinfo=MSK)
    await accept_rules(db_session, first, now)
    await accept_rules(db_session, second, now)
    await accept_video_report(
        db_session,
        telegram_user_id=123,
        message_id=10,
        chat_id=-100,
        thread_id=7,
        file_id="a",
        file_unique_id="same",
        submitted_at=now,
        expected_thread_id=7,
    )

    decision = await accept_video_report(
        db_session,
        telegram_user_id=456,
        message_id=11,
        chat_id=-100,
        thread_id=7,
        file_id="b",
        file_unique_id="same",
        submitted_at=now,
        expected_thread_id=7,
    )

    assert decision.accepted is False
    assert decision.reason == "duplicate_video"


@pytest.mark.asyncio
async def test_rejects_wrong_topic(db_session):
    participant = await upsert_registered_participant(db_session, 123, None, "Участник А.")
    now = datetime(2026, 10, 4, 1, 5, tzinfo=MSK)
    await accept_rules(db_session, participant, now)

    decision = await accept_video_report(
        db_session,
        telegram_user_id=123,
        message_id=10,
        chat_id=-100,
        thread_id=99,
        file_id="a",
        file_unique_id="u",
        submitted_at=now,
        expected_thread_id=7,
    )

    assert decision.accepted is False
    assert decision.reason == "wrong_topic"


@pytest.mark.asyncio
async def test_rejects_report_before_challenge_start(db_session):
    participant = await upsert_registered_participant(db_session, 123, None, "Участник А.")
    await accept_rules(db_session, participant, datetime(2026, 11, 7, 0, 15, tzinfo=MSK))
    participant.challenge_started_at = datetime(2026, 11, 7, 1, 0, tzinfo=MSK)

    decision = await accept_video_report(
        db_session,
        telegram_user_id=123,
        message_id=10,
        chat_id=-100,
        thread_id=7,
        file_id="a",
        file_unique_id="before-start",
        submitted_at=datetime(2026, 11, 7, 0, 30, tzinfo=MSK),
        expected_thread_id=7,
    )

    assert decision.accepted is False
    assert decision.reason == "not_started_yet"
