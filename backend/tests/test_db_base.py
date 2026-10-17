"""Tests for database base declarative models and timestamp mixins."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.base import Base, TimestampMixin
from backend.app.core.db import get_db


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


class CustomColumnModel(Base, TimestampMixin):
    """Model with differing Python attribute name and DB column name."""

    __tablename__ = "custom_column_models"

    display_title: Mapped[str] = mapped_column(
        "title_in_db",
        String(50),
        key="display_title",
        default="default-title",
    )


def test_custom_column_key_mapping() -> None:
    """Verify that models with differing column name and attribute key
    work with defaults and to_dict.
    """
    instance = CustomColumnModel()
    assert instance.display_title == "default-title"
    assert isinstance(instance.id, uuid.UUID)
    data = instance.to_dict()
    assert data["display_title"] == "default-title"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_db_commit_on_success() -> None:
    """Verify get_db commits the session when context exits cleanly."""
    mock_session = AsyncMock()
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session
    mock_factory.return_value.__aexit__.return_value = None

    with patch("backend.app.core.db.async_session_factory", mock_factory):
        gen = get_db()
        session = await gen.asend(None)
        assert session is mock_session
        with pytest.raises(StopAsyncIteration):
            await gen.asend(None)

    mock_session.commit.assert_awaited_once()
    mock_session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_db_rollback_on_exception() -> None:
    """Verify get_db rolls back the session when an exception occurs."""
    mock_session = AsyncMock()
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session
    mock_factory.return_value.__aexit__.return_value = None

    with patch("backend.app.core.db.async_session_factory", mock_factory):
        gen = get_db()
        await gen.asend(None)
        with pytest.raises(RuntimeError, match="DB operation failed"):
            await gen.athrow(RuntimeError("DB operation failed"))

    mock_session.rollback.assert_awaited_once()
    mock_session.commit.assert_not_awaited()
