"""PhoneNumber SQLAlchemy model."""

import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.base import Base, TimestampMixin


class PhoneNumber(Base, TimestampMixin):
    """Inbound and outbound telephone number configuration."""

    __tablename__ = "phone_numbers"
    __table_args__ = (
        Index("ix_phone_numbers_organization_id", "organization_id"),
        Index("ix_phone_numbers_e164", "e164", unique=True),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    e164: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    carrier: Mapped[str] = mapped_column(String(32), nullable=False, default="twilio")
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    trunk_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
