from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChallengeDay, Participant, ParticipantStatus, Report
from app.services.challenge_days import challenge_day_for, challenge_day_window


@dataclass(frozen=True)
class ReportDecision:
    accepted: bool
    reason: str
    participant_id: int | None
    challenge_day: date | None


async def accept_video_report(
    session: AsyncSession,
    *,
    telegram_user_id: int,
    message_id: int,
    chat_id: int,
    thread_id: int | None,
    file_id: str,
    file_unique_id: str,
    submitted_at: datetime,
    expected_thread_id: int,
) -> ReportDecision:
    if thread_id != expected_thread_id:
        return ReportDecision(False, "wrong_topic", None, None)

    participant = await _get_active_participant(session, telegram_user_id)
    if participant is None:
        return ReportDecision(False, "unknown_participant", None, None)
    if participant.challenge_started_at is not None and submitted_at < participant.challenge_started_at:
        return ReportDecision(False, "not_started_yet", participant.id, None)

    duplicate = await session.scalar(
        select(Report.id).where(Report.file_unique_id == file_unique_id).limit(1)
    )
    day = challenge_day_for(submitted_at)
    if duplicate is not None:
        return ReportDecision(False, "duplicate_video", participant.id, day)

    challenge_day = await get_or_create_challenge_day(session, day)
    existing_today = await session.scalar(
        select(Report.id)
        .where(Report.participant_id == participant.id)
        .where(Report.challenge_day_id == challenge_day.id)
        .limit(1)
    )
    if existing_today is not None:
        return ReportDecision(False, "already_reported_today", participant.id, day)

    session.add(
        Report(
            participant_id=participant.id,
            challenge_day_id=challenge_day.id,
            telegram_message_id=message_id,
            telegram_chat_id=chat_id,
            telegram_thread_id=thread_id,
            file_id=file_id,
            file_unique_id=file_unique_id,
            submitted_at=submitted_at,
            accepted_at=submitted_at,
        )
    )
    await session.flush()
    return ReportDecision(True, "accepted", participant.id, day)


async def get_or_create_challenge_day(session: AsyncSession, day: date) -> ChallengeDay:
    result = await session.execute(select(ChallengeDay).where(ChallengeDay.day == day))
    challenge_day = result.scalar_one_or_none()
    if challenge_day is not None:
        return challenge_day

    starts_at, ends_at = challenge_day_window(day)
    challenge_day = ChallengeDay(day=day, starts_at=starts_at, ends_at=ends_at)
    session.add(challenge_day)
    await session.flush()
    return challenge_day


async def accepted_report_names(session: AsyncSession, day: date) -> list[str]:
    result = await session.execute(
        select(Participant.display_name)
        .join(Report, Report.participant_id == Participant.id)
        .join(ChallengeDay, ChallengeDay.id == Report.challenge_day_id)
        .where(ChallengeDay.day == day)
        .order_by(Participant.display_name)
    )
    return list(result.scalars())


async def _get_active_participant(session: AsyncSession, telegram_user_id: int) -> Participant | None:
    result = await session.execute(
        select(Participant)
        .where(Participant.telegram_user_id == telegram_user_id)
        .where(Participant.status == ParticipantStatus.ACTIVE)
    )
    return result.scalar_one_or_none()
