from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.db.models import ParticipantStatus
from app.services.participants import accept_rules, record_rules_acceptance, upsert_registered_participant


@pytest.mark.asyncio
async def test_accept_rules_starts_challenge_immediately(db_session):
    participant = await upsert_registered_participant(
        db_session,
        telegram_user_id=123,
        username="test_user",
        display_name="Тестовый Участник",
    )
    now = datetime(2026, 10, 4, 0, 30, tzinfo=ZoneInfo("Europe/Moscow"))

    updated = await accept_rules(db_session, participant, now)

    assert updated.status == ParticipantStatus.ACTIVE
    assert updated.rules_accepted_at == now
    assert updated.challenge_started_at == now


@pytest.mark.asyncio
async def test_record_rules_acceptance_waits_for_entry_payment(db_session):
    participant = await upsert_registered_participant(
        db_session,
        telegram_user_id=123,
        username="test_user",
        display_name="Тестовый Участник",
    )
    now = datetime(2026, 10, 4, 0, 30, tzinfo=ZoneInfo("Europe/Moscow"))

    updated = await record_rules_acceptance(db_session, participant, now)

    assert updated.status == ParticipantStatus.REGISTERED
    assert updated.rules_accepted_at == now
    assert updated.challenge_started_at is None
