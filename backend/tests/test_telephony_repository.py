"""Tests for TelephonyRepository database queries and tenant isolation."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.telephony.models import PhoneNumber
from backend.app.modules.telephony.repository import TelephonyRepository


@pytest.mark.asyncio
async def test_telephony_repository_lifecycle_in_memory() -> None:
    """Verify repository in-memory fallback create, get, assign, list, and delete."""
    repo = TelephonyRepository()
    org_id = uuid.uuid4()
    e164 = f"+1555{uuid.uuid4().int % 10000000:07d}"

    # 1. Create
    record = await repo.create_phone_number(
        organization_id=org_id,
        e164=e164,
        carrier="twilio",
        trunk_ref="trunk-test-1",
    )
    assert record.e164 == e164
    assert record.organization_id == org_id
    assert record.agent_id is None

    # 2. Get by ID
    fetched = await repo.get_by_id(org_id, record.id)
    assert fetched is not None
    assert fetched.id == record.id

    # 3. Cross-tenant isolation
    foreign_org = uuid.uuid4()
    cross_fetched = await repo.get_by_id(foreign_org, record.id)
    assert cross_fetched is None

    # 4. Get by E.164 (intake lookup)
    by_e164 = await repo.get_by_e164(e164)
    assert by_e164 is not None
    assert by_e164.id == record.id

    # 5. Assign agent
    new_agent_id = uuid.uuid4()
    assigned = await repo.assign_agent(org_id, record.id, new_agent_id)
    assert assigned is not None
    assert assigned.agent_id == new_agent_id

    # 6. List by org
    org_list = await repo.list_by_org(org_id)
    assert len(org_list) >= 1
    assert any(p.id == record.id for p in org_list)

    # 7. Delete
    deleted = await repo.delete_phone_number(org_id, record.id)
    assert deleted is True
    assert await repo.get_by_id(org_id, record.id) is None


@pytest.mark.asyncio
async def test_telephony_repository_db_session_mode() -> None:
    """Verify repository methods interact with AsyncSession properly when provided."""
    mock_session = AsyncMock(spec=AsyncSession)
    repo = TelephonyRepository(session=mock_session)

    org_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    phone_id = uuid.uuid4()
    e164 = "+15559998877"

    # Create phone number in DB mode
    record = await repo.create_phone_number(
        organization_id=org_id,
        e164=e164,
        carrier="twilio",
        agent_id=agent_id,
        trunk_ref="trunk-tw-1",
    )
    assert record.e164 == e164
    assert mock_session.add.called
    assert mock_session.commit.called
    assert mock_session.refresh.called

    # Mock execute return for get_by_id
    fake_phone = PhoneNumber(
        organization_id=org_id,
        e164=e164,
        carrier="twilio",
        agent_id=agent_id,
        trunk_ref="trunk-tw-1",
    )
    fake_phone.id = phone_id
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_phone
    mock_session.execute.return_value = mock_result

    fetched = await repo.get_by_id(org_id, phone_id)
    assert fetched is not None
    assert fetched.id == phone_id
    assert fetched.e164 == e164
