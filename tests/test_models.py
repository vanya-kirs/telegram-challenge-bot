from sqlalchemy import UniqueConstraint

from app.db.models import (
    Participant,
    ParticipantStatus,
    PaymentPurpose,
    PaymentRequest,
    PaymentStatus,
    Report,
)


def test_participant_defaults():
    participant = Participant(
        telegram_user_id=123,
        display_name="Участник А.",
        status=ParticipantStatus.REGISTERED,
    )

    assert participant.penalty_step == 0
    assert participant.current_debt_rub == 0


def test_report_table_has_unique_file_unique_id():
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in Report.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("file_unique_id",) in unique_columns


def test_payment_status_values_are_stable():
    assert PaymentStatus.PENDING.value == "pending"
    assert PaymentStatus.CONFIRMED.value == "confirmed"
    assert PaymentStatus.REJECTED.value == "rejected"


def test_payment_status_column_uses_lowercase_values():
    assert PaymentRequest.__table__.c.status.type.enums == ["pending", "confirmed", "rejected"]


def test_payment_purpose_values_are_stable():
    assert PaymentPurpose.DEBT.value == "debt"
    assert PaymentPurpose.ENTRY_FEE.value == "entry_fee"


def test_payment_purpose_column_uses_lowercase_values():
    assert PaymentRequest.__table__.c.purpose.type.enums == ["debt", "entry_fee"]
