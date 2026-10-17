"""Tests for health check endpoints."""

import pytest
from httpx import AsyncClient

from backend.app.core import db


@pytest.mark.asyncio
async def test_health_live(async_client: AsyncClient) -> None:
    """Verify that liveness probe returns 200 and status ok."""
    response = await async_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_ready_mocked(
    monkeypatch: pytest.MonkeyPatch,
    async_client: AsyncClient,
) -> None:
    """Verify that readiness probe returns 200 when all dependencies are healthy."""

    async def fake_check_db() -> bool:
        return True

    async def fake_check_redis() -> bool:
        return True

    monkeypatch.setattr(db, "check_db_ready", fake_check_db)
    monkeypatch.setattr(db, "check_redis_ready", fake_check_redis)

    response = await async_client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "dependencies": {
            "database": "ok",
            "redis": "ok",
        },
    }


@pytest.mark.asyncio
async def test_health_ready_degraded_db(
    monkeypatch: pytest.MonkeyPatch,
    async_client: AsyncClient,
) -> None:
    """Verify that readiness probe returns 503 degraded when database check fails."""

    async def fake_check_db() -> bool:
        return False

    async def fake_check_redis() -> bool:
        return True

    monkeypatch.setattr(db, "check_db_ready", fake_check_db)
    monkeypatch.setattr(db, "check_redis_ready", fake_check_redis)

    response = await async_client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "dependencies": {
            "database": "unreachable",
            "redis": "ok",
        },
    }


@pytest.mark.asyncio
async def test_health_ready_degraded_redis(
    monkeypatch: pytest.MonkeyPatch,
    async_client: AsyncClient,
) -> None:
    """Verify that readiness probe returns 503 degraded when redis check fails."""

    async def fake_check_db() -> bool:
        return True

    async def fake_check_redis() -> bool:
        return False

    monkeypatch.setattr(db, "check_db_ready", fake_check_db)
    monkeypatch.setattr(db, "check_redis_ready", fake_check_redis)

    response = await async_client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "dependencies": {
            "database": "ok",
            "redis": "unreachable",
        },
    }
