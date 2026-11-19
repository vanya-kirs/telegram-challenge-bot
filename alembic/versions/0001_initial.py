"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "participants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=512), nullable=False),
        sa.Column("status", sa.Enum("registered", "active", "removed", "left", "blocked", name="participant_status", native_enum=False), nullable=False),
        sa.Column("rules_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("challenge_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("joined_group_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("left_group_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("penalty_step", sa.Integer(), nullable=False),
        sa.Column("current_debt_rub", sa.Integer(), nullable=False),
        sa.Column("debt_started_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_user_id"),
    )
    op.create_index(op.f("ix_participants_telegram_user_id"), "participants", ["telegram_user_id"], unique=False)

    op.create_table(
        "challenge_days",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("list_message_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("list_message_thread_id", sa.Integer(), nullable=True),
        sa.Column("list_message_id", sa.Integer(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day"),
    )
    op.create_index(op.f("ix_challenge_days_day"), "challenge_days", ["day"], unique=False)

    op.create_table(
        "invite_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=False),
        sa.Column("invite_link", sa.Text(), nullable=False),
        sa.Column("telegram_invite_link_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invite_links_participant_id"), "invite_links", ["participant_id"], unique=False)

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=False),
        sa.Column("challenge_day_id", sa.Integer(), nullable=False),
        sa.Column("telegram_message_id", sa.Integer(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_thread_id", sa.Integer(), nullable=True),
        sa.Column("file_id", sa.Text(), nullable=False),
        sa.Column("file_unique_id", sa.String(length=255), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["challenge_day_id"], ["challenge_days.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_unique_id", name="uq_reports_file_unique_id"),
        sa.UniqueConstraint("participant_id", "challenge_day_id", name="uq_reports_participant_day"),
    )
    op.create_index(op.f("ix_reports_challenge_day_id"), "reports", ["challenge_day_id"], unique=False)
    op.create_index(op.f("ix_reports_participant_id"), "reports", ["participant_id"], unique=False)

    op.create_table(
        "misses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=False),
        sa.Column("challenge_day_id", sa.Integer(), nullable=False),
        sa.Column("penalty_step", sa.Integer(), nullable=False),
        sa.Column("amount_rub", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["challenge_day_id"], ["challenge_days.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("participant_id", "challenge_day_id", name="uq_misses_participant_day"),
    )
    op.create_index(op.f("ix_misses_challenge_day_id"), "misses", ["challenge_day_id"], unique=False)
    op.create_index(op.f("ix_misses_participant_id"), "misses", ["participant_id"], unique=False)

    op.create_table(
        "payment_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.Enum("debt", "entry_fee", name="payment_purpose", native_enum=False), nullable=False),
        sa.Column("status", sa.Enum("pending", "confirmed", "rejected", name="payment_status", native_enum=False), nullable=False),
        sa.Column("amount_rub_at_submission", sa.Integer(), nullable=False),
        sa.Column("proof_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("proof_message_id", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("handled_by_admin_id", sa.BigInteger(), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admin_comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payment_requests_participant_id"), "payment_requests", ["participant_id"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_events_event_type"), "audit_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_audit_events_participant_id"), "audit_events", ["participant_id"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("payment_requests")
    op.drop_table("misses")
    op.drop_table("reports")
    op.drop_table("invite_links")
    op.drop_table("challenge_days")
    op.drop_table("participants")
