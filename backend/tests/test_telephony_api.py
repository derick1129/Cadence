"""Tests for authenticated customer telephony REST API endpoints."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.security import create_access_token
from backend.app.main import app


@pytest.mark.asyncio
async def test_telephony_api_crud_flow() -> None:
    """Verify phone numbers provisioning, listing, agent assignment, and release."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    token = create_access_token(data={"sub": str(user_id), "org": str(org_id), "role": "admin"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register phone number
        e164 = f"+1555{uuid.uuid4().int % 10000000:07d}"
        res_create = await client.post(
            "/v1/phone-numbers",
            headers={"Authorization": f"Bearer {token}"},
            json={"e164": e164, "carrier": "twilio"},
        )
        assert res_create.status_code == 201
        created = res_create.json()
        phone_id = created["id"]
        assert created["e164"] == e164
        assert created["agent_id"] is None

        # 2. List numbers
        res_list = await client.get(
            "/v1/phone-numbers",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_list.status_code == 200
        numbers = res_list.json()
        assert any(n["id"] == phone_id for n in numbers)

        # 3. Assign agent
        new_agent_id = str(uuid.uuid4())
        res_patch = await client.patch(
            f"/v1/phone-numbers/{phone_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"agent_id": new_agent_id},
        )
        assert res_patch.status_code == 200
        assert res_patch.json()["agent_id"] == new_agent_id

        # 4. Delete phone number
        res_del = await client.delete(
            f"/v1/phone-numbers/{phone_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_del.status_code == 204
