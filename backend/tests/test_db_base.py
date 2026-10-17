"""Tests for database base declarative models and timestamp mixins."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.base import Base, TimestampMixin


class SampleModel(Base, TimestampMixin):
    """Concrete sample model for verifying base mappings."""

    __tablename__ = "sample_test_models"

    name: Mapped[str] = mapped_column(String(50), nullable=False)


def test_base_metadata_and_attributes() -> None:
    """Verify that models inheriting from Base and TimestampMixin
    have default UUID and timestamps.
    """
    instance = SampleModel(name="test-item")
    assert instance.name == "test-item"
    assert isinstance(instance.id, uuid.UUID)
    assert isinstance(instance.created_at, datetime)
    assert isinstance(instance.updated_at, datetime)
    assert instance.created_at.tzinfo == UTC
    assert instance.to_dict()["name"] == "test-item"
    assert "id" in instance.to_dict()
