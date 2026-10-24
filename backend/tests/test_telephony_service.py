"""Tests for TelephonyService business logic, E.164 normalization, and calling windows."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

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


@pytest.mark.asyncio
async def test_telephony_service_create_normalization() -> None:
    """Verify service normalizes E.164 string through telephony provider."""
    service = TelephonyService(repository=None)

    # Malformed E.164 raises ValueError
    with pytest.raises(ValueError, match="Invalid E.164"):
        service.normalize_number("12345")

    assert service.normalize_number(" +1 (555) 019-2831 ") == "+15550192831"
