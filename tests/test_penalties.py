from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.participants import accept_rules, upsert_registered_participant
from app.services.penalties import charge_missing_reports_for_day, debt_age_days, is_removal_due


MSK = ZoneInfo("Europe/Moscow")


@pytest.mark.asyncio
async def test_first_miss_charges_500(db_session, challenge_day):
    participant = await upsert_registered_participant(db_session, 123, None, "Участник А.")
    await accept_rules(db_session, participant, datetime(2026, 10, 4, 0, 30, tzinfo=MSK))

    result = await charge_missing_reports_for_day(db_session, challenge_day, penalty_step_rub=500)

    assert result.charged_count == 1
    assert participant.penalty_step == 1
    assert participant.current_debt_rub == 500


@pytest.mark.asyncio
async def test_close_day_is_idempotent(db_session, challenge_day):
    participant = await upsert_registered_participant(db_session, 123, None, "Участник А.")
    await accept_rules(db_session, participant, datetime(2026, 10, 4, 0, 30, tzinfo=MSK))

    first = await charge_missing_reports_for_day(db_session, challenge_day, penalty_step_rub=500)
    second = await charge_missing_reports_for_day(db_session, challenge_day, penalty_step_rub=500)

    assert first.charged_count == 1
    assert second.charged_count == 0
    assert participant.penalty_step == 1
    assert participant.current_debt_rub == 500


def test_debt_age_and_removal_due():
    class ParticipantStub:
        debt_started_on = date(2026, 10, 1)
        current_debt_rub = 500

    participant = ParticipantStub()

    assert debt_age_days(participant, date(2026, 10, 3)) == 3
    assert is_removal_due(participant, date(2026, 10, 4)) is True
