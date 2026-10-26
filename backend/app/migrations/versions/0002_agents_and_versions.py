"""agents_and_versions

Revision ID: 0002_agents_and_versions
Revises: 0001_initial_auth_and_tenancy
Create Date: 2026-10-20 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op  # type: ignore[import-not-found]
from sqlalchemy.dialects import postgresql

revision: str = "0002_agents_and_versions"
down_revision: str | None = "0001_initial_auth_and_tenancy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agents_organization_id", "agents", ["organization_id"])

    op.create_table(
        "agent_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("greeting", sa.Text(), nullable=True),
        sa.Column("stt_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("llm_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tts_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("silence_timeout_s", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("max_duration_s", sa.Integer(), nullable=False, server_default="600"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("agent_id", "version_no", name="uq_agent_version_no"),
    )
    op.create_index("ix_agent_versions_agent_id", "agent_versions", ["agent_id"])

    op.create_foreign_key(
        "fk_agents_current_version",
        "agents",
        "agent_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )


def downgrade() -> None:
    op.drop_constraint("fk_agents_current_version", "agents", type_="foreignkey")
    op.drop_table("agent_versions")
    op.drop_table("agents")
