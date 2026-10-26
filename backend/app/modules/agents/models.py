"""Agent and AgentVersion SQLAlchemy models."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.base import Base, TimestampMixin


class Agent(Base, TimestampMixin):
    """Voice agent entity scoped strictly to an organization tenant."""

    __tablename__ = "agents"
    __table_args__ = (Index("ix_agents_organization_id", "organization_id"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "agent_versions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_agents_current_version",
        ),
        nullable=True,
    )


class AgentVersion(Base, TimestampMixin):
    """Immutable version configuration of an agent."""

    __tablename__ = "agent_versions"
    __table_args__ = (
        UniqueConstraint("agent_id", "version_no", name="uq_agent_version_no"),
        Index("ix_agent_versions_agent_id", "agent_id"),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    greeting: Mapped[str | None] = mapped_column(Text, nullable=True)
    stt_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    llm_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    tts_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    silence_timeout_s: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    max_duration_s: Mapped[int] = mapped_column(Integer, default=600, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
