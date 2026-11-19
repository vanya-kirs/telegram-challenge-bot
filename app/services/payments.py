from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Participant, ParticipantStatus, PaymentPurpose, PaymentRequest, PaymentStatus
from app.services.challenge_days import next_challenge_start


@dataclass(frozen=True)
class PaymentDecision:
    changed: bool
    status: PaymentStatus
    participant_id: int
    purpose: PaymentPurpose
    should_send_reinvite: bool = False
    should_unban: bool = False


async def create_payment_request(
    session: AsyncSession,
    participant_id: int,
    proof_chat_id: int,
    proof_message_id: int,
    submitted_at: datetime,
    purpose: PaymentPurpose = PaymentPurpose.DEBT,
    amount_rub: int | None = None,
) -> PaymentRequest:
    participant = await session.get(Participant, participant_id)
    if participant is None:
        raise ValueError("participant must exist")
    request = PaymentRequest(
        participant_id=participant.id,
        purpose=purpose,
        status=PaymentStatus.PENDING,
        amount_rub_at_submission=participant.current_debt_rub if amount_rub is None else amount_rub,
        proof_chat_id=proof_chat_id,
        proof_message_id=proof_message_id,
        submitted_at=submitted_at,
    )
    session.add(request)
    await session.flush()
    return request


async def confirm_payment(
    session: AsyncSession,
    payment_request_id: int,
    admin_id: int,
    handled_at: datetime,
    timezone: str = "Europe/Moscow",
) -> PaymentDecision:
    result = await session.execute(
        update(PaymentRequest)
        .where(PaymentRequest.id == payment_request_id)
        .where(PaymentRequest.status == PaymentStatus.PENDING)
        .values(
            status=PaymentStatus.CONFIRMED,
            handled_by_admin_id=admin_id,
            handled_at=handled_at,
        )
        .returning(PaymentRequest.participant_id)
    )
    participant_id = result.scalar_one_or_none()
    request = await session.get(PaymentRequest, payment_request_id, populate_existing=True)
    if request is None:
        raise ValueError("payment request must exist")
    if participant_id is None:
        return PaymentDecision(False, request.status, request.participant_id, request.purpose)

    participant = await session.get(Participant, participant_id)
    if participant is None:
        raise ValueError("participant must exist")

    was_removed = participant.status == ParticipantStatus.REMOVED
    should_send_invite = request.purpose == PaymentPurpose.ENTRY_FEE or was_removed
    if request.purpose == PaymentPurpose.DEBT:
        participant.current_debt_rub = 0
        participant.debt_started_on = None
    if should_send_invite:
        participant.status = ParticipantStatus.ACTIVE
        if request.purpose == PaymentPurpose.ENTRY_FEE:
            participant.challenge_started_at = next_challenge_start(handled_at, timezone)
        else:
            participant.challenge_started_at = participant.challenge_started_at or handled_at
    await session.flush()
    return PaymentDecision(
        True,
        request.status,
        participant.id,
        request.purpose,
        should_send_invite,
        should_unban=was_removed,
    )


async def reject_payment(
    session: AsyncSession,
    payment_request_id: int,
    admin_id: int,
    handled_at: datetime,
) -> PaymentDecision:
    result = await session.execute(
        update(PaymentRequest)
        .where(PaymentRequest.id == payment_request_id)
        .where(PaymentRequest.status == PaymentStatus.PENDING)
        .values(
            status=PaymentStatus.REJECTED,
            handled_by_admin_id=admin_id,
            handled_at=handled_at,
        )
        .returning(PaymentRequest.participant_id)
    )
    participant_id = result.scalar_one_or_none()
    request = await session.get(PaymentRequest, payment_request_id, populate_existing=True)
    if request is None:
        raise ValueError("payment request must exist")
    if participant_id is None:
        return PaymentDecision(False, request.status, request.participant_id, request.purpose)

    await session.flush()
    return PaymentDecision(True, request.status, request.participant_id, request.purpose)
