"""sessions_records

Revision ID: 0004_sessions_records
Revises: 0003_sessions
Create Date: 2026-10-20 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op  # type: ignore[import-not-found]
from sqlalchemy.dialects import postgresql

revision: str = "0004_sessions_records"
down_revision: str | None = "0003_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transcript_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("started_at_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_transcript_segments_session_seq", "transcript_segments", ["session_id", "seq"]
    )

    op.create_table(
        "session_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("avg_latency_ms", sa.Integer(), nullable=True),
        sa.Column("p95_latency_ms", sa.Integer(), nullable=True),
        sa.Column("interruption_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stt_seconds_billed", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tts_characters_billed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", name="uq_session_metrics_session_id"),
    )


def downgrade() -> None:
    op.drop_table("session_metrics")
    op.drop_table("transcript_segments")
