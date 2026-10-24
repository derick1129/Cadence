"""telephony

Revision ID: 0006_telephony
Revises: 0005_tools_and_audit
Create Date: 2026-10-24 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op  # type: ignore[import-not-found]
from sqlalchemy.dialects import postgresql

revision: str = "0006_telephony"
down_revision: str | None = "0005_tools_and_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "phone_numbers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("e164", sa.String(length=32), nullable=False),
        sa.Column("carrier", sa.String(length=32), nullable=False, server_default="twilio"),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("trunk_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("e164", name="uq_phone_numbers_e164"),
    )
    op.create_index("ix_phone_numbers_organization_id", "phone_numbers", ["organization_id"])
    op.create_index("ix_phone_numbers_e164", "phone_numbers", ["e164"], unique=True)


def downgrade() -> None:
    op.drop_table("phone_numbers")
