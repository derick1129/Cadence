"""Session SQLAlchemy models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.base import Base, TimestampMixin


class Session(Base, TimestampMixin):
    """Voice conversation session entity."""

    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_organization_id", "organization_id"),
        Index("ix_sessions_room_name", "room_name", unique=True),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(16), default="web", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="initiated", nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    outcome_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    room_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_s: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recording_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
