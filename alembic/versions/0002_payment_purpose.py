"""add payment purpose

Revision ID: 0002_payment_purpose
Revises: 0001_initial
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_payment_purpose"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("payment_requests")}
    if "purpose" in columns:
        return
    op.add_column(
        "payment_requests",
        sa.Column(
            "purpose",
            sa.Enum("debt", "entry_fee", name="payment_purpose", native_enum=False),
            nullable=False,
            server_default="debt",
        ),
    )
    op.alter_column("payment_requests", "purpose", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("payment_requests")}
    if "purpose" not in columns:
        return
    op.drop_column("payment_requests", "purpose")
