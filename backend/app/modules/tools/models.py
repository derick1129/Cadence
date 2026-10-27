"""Tool, AgentTool, and ToolCall SQLAlchemy models."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.base import Base, TimestampMixin


class Tool(Base, TimestampMixin):
    """Custom webhook or telephony transfer tool entity."""

    __tablename__ = "tools"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_tools_org_name"),
        Index("ix_tools_organization_id", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)  # "http" or "transfer"
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    json_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    outcome_label: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AgentTool(Base):
    """Association table linking an immutable agent version to an available tool."""

    __tablename__ = "agent_tools"

    agent_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_versions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tools.id", ondelete="CASCADE"),
        primary_key=True,
    )


class ToolCall(Base, TimestampMixin):
    """Audit log record for an executed tool invocation during a session."""

    __tablename__ = "tool_calls"
    __table_args__ = (Index("ix_tool_calls_session_id", "session_id"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tools.id", ondelete="SET NULL"),
        nullable=True,
    )
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="success", nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
