"""SQLAlchemy declarative base and common model mixins."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """Return current timestamp in UTC timezone."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    def to_dict(self) -> dict[str, Any]:
        """Convert mapped attributes into a dictionary."""
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}


@event.listens_for(Base, "init", propagate=True)
def _init_defaults(target: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    """Populate default values on model instantiation if not provided."""
    if hasattr(target, "__table__"):
        for col in target.__table__.columns:
            if col.name not in kwargs and col.default is not None:
                arg = col.default.arg
                if callable(arg):
                    try:
                        kwargs[col.name] = arg(None)
                    except Exception:
                        pass
                elif not hasattr(arg, "__clause_element__"):
                    kwargs[col.name] = arg


class TimestampMixin:
    """Mixin providing UUID primary key and standard UTC created_at/updated_at timestamps."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )
