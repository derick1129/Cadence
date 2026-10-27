"""Cross-tenant penetration tests for telephony phone numbers."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.security import create_access_token
from backend.app.main import app


@pytest.mark.asyncio
async def test_cross_tenant_phone_number_isolation() -> None:
    """Ensure Organization B cannot view, modify, or delete numbers owned by Organization A."""
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    token_a = create_access_token(
        data={"sub": str(uuid.uuid4()), "org": str(org_a), "role": "admin"}
    )
    token_b = create_access_token(
        data={"sub": str(uuid.uuid4()), "org": str(org_b), "role": "admin"}
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Org A provisions a number
        e164 = f"+1555{uuid.uuid4().int % 10000000:07d}"
        res = await client.post(
            "/v1/phone-numbers",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"e164": e164, "carrier": "twilio"},
        )
        assert res.status_code == 201
        phone_id = res.json()["id"]

        # Org B attempts to read
        res_b_get = await client.get(
            f"/v1/phone-numbers/{phone_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert res_b_get.status_code == 404

        # Org B attempts to reassign agent
        res_b_patch = await client.patch(
            f"/v1/phone-numbers/{phone_id}",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"agent_id": str(uuid.uuid4())},
        )
        assert res_b_patch.status_code == 404

        # Org B attempts to delete
        res_b_del = await client.delete(
            f"/v1/phone-numbers/{phone_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert res_b_del.status_code == 404
