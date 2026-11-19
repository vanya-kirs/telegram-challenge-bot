from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Participant, ParticipantStatus


async def upsert_registered_participant(
    session: AsyncSession,
    telegram_user_id: int,
    username: str | None,
    display_name: str,
) -> Participant:
    result = await session.execute(
        select(Participant).where(Participant.telegram_user_id == telegram_user_id)
    )
    participant = result.scalar_one_or_none()
    first_name, last_name = split_display_name(display_name)
    if participant is None:
        participant = Participant(
            telegram_user_id=telegram_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            display_name=display_name,
            status=ParticipantStatus.REGISTERED,
        )
        session.add(participant)
    else:
        participant.username = username
        participant.first_name = first_name
        participant.last_name = last_name
        participant.display_name = display_name
        if participant.status == ParticipantStatus.BLOCKED:
            participant.status = ParticipantStatus.REGISTERED

    await session.flush()
    return participant


async def accept_rules(session: AsyncSession, participant: Participant, now: datetime) -> Participant:
    participant.status = ParticipantStatus.ACTIVE
    participant.rules_accepted_at = now
    participant.challenge_started_at = participant.challenge_started_at or now
    await session.flush()
    return participant


async def record_rules_acceptance(session: AsyncSession, participant: Participant, now: datetime) -> Participant:
    participant.rules_accepted_at = now
    if participant.status == ParticipantStatus.BLOCKED:
        participant.status = ParticipantStatus.REGISTERED
    await session.flush()
    return participant


async def mark_joined_group(
    session: AsyncSession,
    telegram_user_id: int,
    joined_at: datetime,
) -> Participant | None:
    result = await session.execute(
        select(Participant).where(Participant.telegram_user_id == telegram_user_id)
    )
    participant = result.scalar_one_or_none()
    if participant is None:
        return None
    participant.joined_group_at = joined_at
    participant.left_group_at = None
    if participant.status in {ParticipantStatus.REGISTERED, ParticipantStatus.LEFT, ParticipantStatus.REMOVED}:
        participant.status = ParticipantStatus.ACTIVE
    await session.flush()
    return participant


def split_display_name(display_name: str) -> tuple[str | None, str | None]:
    parts = display_name.strip().split(maxsplit=1)
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]
