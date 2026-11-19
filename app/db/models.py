from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class ParticipantStatus(StrEnum):
    REGISTERED = "registered"
    ACTIVE = "active"
    REMOVED = "removed"
    LEFT = "left"
    BLOCKED = "blocked"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class PaymentPurpose(StrEnum):
    DEBT = "debt"
    ENTRY_FEE = "entry_fee"


def enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(512))
    status: Mapped[ParticipantStatus] = mapped_column(
        Enum(
            ParticipantStatus,
            name="participant_status",
            native_enum=False,
            values_callable=enum_values,
        ),
        default=ParticipantStatus.REGISTERED,
    )
    rules_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    challenge_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    joined_group_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    left_group_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    penalty_step: Mapped[int] = mapped_column(Integer, default=0)
    current_debt_rub: Mapped[int] = mapped_column(Integer, default=0)
    debt_started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    invite_links: Mapped[list[InviteLink]] = relationship(back_populates="participant", cascade="all, delete-orphan")
    reports: Mapped[list[Report]] = relationship(back_populates="participant", cascade="all, delete-orphan")
    misses: Mapped[list[Miss]] = relationship(back_populates="participant", cascade="all, delete-orphan")
    payment_requests: Mapped[list[PaymentRequest]] = relationship(back_populates="participant", cascade="all, delete-orphan")
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="participant", cascade="all, delete-orphan")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if self.penalty_step is None:
            self.penalty_step = 0
        if self.current_debt_rub is None:
            self.current_debt_rub = 0


class InviteLink(Base):
    __tablename__ = "invite_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    invite_link: Mapped[str] = mapped_column(Text)
    telegram_invite_link_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    participant: Mapped[Participant] = relationship(back_populates="invite_links")


class ChallengeDay(Base):
    __tablename__ = "challenge_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(Date, unique=True, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    list_message_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    list_message_thread_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    list_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    reports: Mapped[list[Report]] = relationship(back_populates="challenge_day", cascade="all, delete-orphan")
    misses: Mapped[list[Miss]] = relationship(back_populates="challenge_day", cascade="all, delete-orphan")


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("participant_id", "challenge_day_id", name="uq_reports_participant_day"),
        UniqueConstraint("file_unique_id", name="uq_reports_file_unique_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    challenge_day_id: Mapped[int] = mapped_column(ForeignKey("challenge_days.id", ondelete="CASCADE"), index=True)
    telegram_message_id: Mapped[int] = mapped_column(Integer)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger)
    telegram_thread_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_id: Mapped[str] = mapped_column(Text)
    file_unique_id: Mapped[str] = mapped_column(String(255))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    participant: Mapped[Participant] = relationship(back_populates="reports")
    challenge_day: Mapped[ChallengeDay] = relationship(back_populates="reports")


class Miss(Base):
    __tablename__ = "misses"
    __table_args__ = (UniqueConstraint("participant_id", "challenge_day_id", name="uq_misses_participant_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    challenge_day_id: Mapped[int] = mapped_column(ForeignKey("challenge_days.id", ondelete="CASCADE"), index=True)
    penalty_step: Mapped[int] = mapped_column(Integer)
    amount_rub: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    participant: Mapped[Participant] = relationship(back_populates="misses")
    challenge_day: Mapped[ChallengeDay] = relationship(back_populates="misses")


class PaymentRequest(Base):
    __tablename__ = "payment_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[PaymentPurpose] = mapped_column(
        Enum(
            PaymentPurpose,
            name="payment_purpose",
            native_enum=False,
            values_callable=enum_values,
        ),
        default=PaymentPurpose.DEBT,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(
            PaymentStatus,
            name="payment_status",
            native_enum=False,
            values_callable=enum_values,
        ),
        default=PaymentStatus.PENDING,
    )
    amount_rub_at_submission: Mapped[int] = mapped_column(Integer)
    proof_chat_id: Mapped[int] = mapped_column(BigInteger)
    proof_message_id: Mapped[int] = mapped_column(Integer)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    handled_by_admin_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admin_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    participant: Mapped[Participant] = relationship(back_populates="payment_requests")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int | None] = mapped_column(ForeignKey("participants.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(255), index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    participant: Mapped[Participant | None] = relationship(back_populates="audit_events")
