"""sessions

Revision ID: 0003_sessions
Revises: 0002_agents_and_versions
Create Date: 2026-10-20 10:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op  # type: ignore[import-not-found]
from sqlalchemy.dialects import postgresql

revision: str = "0003_sessions"
down_revision: str | None = "0002_agents_and_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(length=16), nullable=False, server_default="web"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="initiated"),
        sa.Column("outcome", sa.String(length=32), nullable=True),
        sa.Column("outcome_label", sa.String(length=64), nullable=True),
        sa.Column("room_name", sa.String(length=255), unique=True, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_s", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recording_key", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_organization_id", "sessions", ["organization_id"])
    op.create_index("ix_sessions_room_name", "sessions", ["room_name"], unique=True)


def downgrade() -> None:
    op.drop_table("sessions")
