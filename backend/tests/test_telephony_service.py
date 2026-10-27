"""Tests for TelephonyService business logic, E.164 normalization, and calling windows."""

import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from backend.app.modules.telephony.schemas import PhoneNumberAssign, PhoneNumberCreate
from backend.app.modules.telephony.service import (
    TelephonyService,
    is_within_calling_window,
)


def test_calling_window_enforcement() -> None:
    """Verify outbound/inbound telephone calling window (8:00 AM - 8:00 PM local time)."""
    tz = "America/New_York"

    # 10:00 AM EST -> Permitted
    dt_valid = datetime(2026, 10, 24, 10, 0, tzinfo=ZoneInfo(tz))
    assert is_within_calling_window(now=dt_valid, tz_name=tz) is True

    # 7:59 AM EST -> Blocked (too early)
    dt_early = datetime(2026, 10, 24, 7, 59, tzinfo=ZoneInfo(tz))
    assert is_within_calling_window(now=dt_early, tz_name=tz) is False

    # 8:01 PM EST -> Blocked (too late)
    dt_late = datetime(2026, 10, 24, 20, 1, tzinfo=ZoneInfo(tz))
    assert is_within_calling_window(now=dt_late, tz_name=tz) is False


def test_calling_window_fallback_invalid_tz() -> None:
    """Verify fallback to UTC when invalid timezone name is passed."""
    dt_utc_valid = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    assert is_within_calling_window(now=dt_utc_valid, tz_name="Invalid/Timezone") is True


@pytest.mark.asyncio
async def test_telephony_service_create_normalization() -> None:
    """Verify service normalizes E.164 string through telephony provider."""
    service = TelephonyService(repository=None)

    # Malformed E.164 raises ValueError
    with pytest.raises(ValueError, match="Invalid E.164"):
        service.normalize_number("12345")

    assert service.normalize_number(" +1 (555) 019-2831 ") == "+15550192831"


@pytest.mark.asyncio
async def test_telephony_service_lifecycle() -> None:
    """Verify end-to-end service lifecycle: create, get, assign, list, and delete."""
    service = TelephonyService()
    org_id = uuid.uuid4()
    e164 = f"+1555{uuid.uuid4().int % 10000000:07d}"

    # 1. Create
    created = await service.create_phone_number(
        organization_id=org_id,
        payload=PhoneNumberCreate(e164=e164, carrier="twilio"),
    )
    assert created.e164 == e164
    assert created.organization_id == org_id
    assert created.trunk_ref is not None

    # 2. Get by ID & E.164
    fetched = await service.get_phone_number(org_id, created.id)
    assert fetched is not None
    assert fetched.id == created.id

    by_e164 = await service.get_by_e164(e164)
    assert by_e164 is not None
    assert by_e164.id == created.id

    # 3. Assign agent
    agent_id = uuid.uuid4()
    assigned = await service.assign_agent(
        organization_id=org_id,
        phone_number_id=created.id,
        data=PhoneNumberAssign(agent_id=agent_id),
    )
    assert assigned is not None
    assert assigned.agent_id == agent_id

    # 4. List
    numbers = await service.list_phone_numbers(org_id)
    assert len(numbers) >= 1
    assert any(n.id == created.id for n in numbers)

    # 5. Delete
    deleted = await service.delete_phone_number(org_id, created.id)
    assert deleted is True
    assert await service.get_phone_number(org_id, created.id) is None
