"""Pytest fixtures for backend test suite."""

import sys
from collections.abc import AsyncGenerator
from pathlib import Path

# Ensure repository root is on sys.path so 'backend' can be imported
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from backend.app.main import app  # noqa: E402


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an asynchronous HTTP client configured with ASGITransport."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def client(async_client: AsyncClient) -> AsyncClient:
    """Convenience alias for async_client."""
    return async_client
