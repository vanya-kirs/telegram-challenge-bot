from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChallengeDay, Miss, Participant, ParticipantStatus, Report


@dataclass(frozen=True)
class ChargeMissingReportsResult:
    charged_count: int
    total_amount_rub: int


async def charge_missed_day(
    session: AsyncSession,
    participant_id: int,
    challenge_day_id: int,
    penalty_step_rub: int,
) -> Miss:
    participant = await session.get(Participant, participant_id)
    challenge_day = await session.get(ChallengeDay, challenge_day_id)
    if participant is None or challenge_day is None:
        raise ValueError("participant and challenge day must exist")

    existing = await session.scalar(
        select(Miss.id)
        .where(Miss.participant_id == participant_id)
        .where(Miss.challenge_day_id == challenge_day_id)
        .limit(1)
    )
    if existing is not None:
        raise ValueError("miss already charged for this day")

    participant.penalty_step += 1
    amount = participant.penalty_step * penalty_step_rub
    participant.current_debt_rub += amount
    if participant.debt_started_on is None:
        participant.debt_started_on = challenge_day.day

    miss = Miss(
        participant_id=participant_id,
        challenge_day_id=challenge_day_id,
        penalty_step=participant.penalty_step,
        amount_rub=amount,
    )
    session.add(miss)
    await session.flush()
    return miss


async def charge_missing_reports_for_day(
    session: AsyncSession,
    challenge_day: ChallengeDay,
    penalty_step_rub: int,
) -> ChargeMissingReportsResult:
    result = await session.execute(
        select(Participant).where(Participant.status == ParticipantStatus.ACTIVE)
    )
    charged_count = 0
    total_amount = 0

    for participant in result.scalars():
        if participant.challenge_started_at is None:
            continue
        if participant.challenge_started_at >= challenge_day.ends_at:
            continue
        has_report = await session.scalar(
            select(Report.id)
            .where(Report.participant_id == participant.id)
            .where(Report.challenge_day_id == challenge_day.id)
            .limit(1)
        )
        if has_report is not None:
            continue
        has_miss = await session.scalar(
            select(Miss.id)
            .where(Miss.participant_id == participant.id)
            .where(Miss.challenge_day_id == challenge_day.id)
            .limit(1)
        )
        if has_miss is not None:
            continue

        miss = await charge_missed_day(session, participant.id, challenge_day.id, penalty_step_rub)
        charged_count += 1
        total_amount += miss.amount_rub

    return ChargeMissingReportsResult(charged_count=charged_count, total_amount_rub=total_amount)


def debt_age_days(participant: Participant, today: date) -> int:
    if participant.current_debt_rub <= 0 or participant.debt_started_on is None:
        return 0
    return (today - participant.debt_started_on).days + 1


def is_removal_due(participant: Participant, today: date) -> bool:
    return debt_age_days(participant, today) >= 4
