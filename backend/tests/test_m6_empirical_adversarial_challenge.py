"""Empirical adversarial and stress test suite for Milestone M6 (Inbound Phone & Telephony).

This test suite rigorously challenges:
1. E.164 normalization & validation edge cases:
   - Valid whitespace, hyphens, parentheses, international country codes
     (+1, +44, +49, +81, +33, +91).
   - Minimum (2 digits) and maximum (15 digits) lengths per ITU-T E.164.
   - Adversarial rejections: letters, missing plus, leading zero in country code, 16+ digits,
     empty/whitespace, plus-only, symbols, unicode digits, SQL injection, XSS payloads.
   - HTTP API rejection (400 / 422) on POST /v1/phone-numbers with invalid formats.
2. TCPA calling window boundaries (8:00 AM to 8:00 PM recipient local time):
   - Exact boundary seconds: 07:59:58 (False), 07:59:59 (False), 08:00:00 (True), 08:00:01 (True),
     19:59:59 (True), 20:00:00 (True), 20:00:01 (False), 20:00:00.000001 (False).
   - Cross-timezone evaluations: America/New_York, America/Los_Angeles, UTC, Asia/Tokyo,
     Europe/London, Australia/Sydney.
   - Simultaneous instant test: one UTC moment that is legal in NY but prohibited in LA.
   - Resilience against invalid timezones and None timestamp.
3. Inbound SIP dispatch (/internal/sip/inbound):
   - Authentication security: missing, invalid, or forged X-Internal-Service-Token (401).
   - Unassigned phone number routing (404).
   - Dialing unknown/unregistered numbers (404).
   - Unversioned agent routing (400).
   - Deleted/non-existent agent routing (400).
   - Full successful dispatch payload: room_name, session_id, livekit_url,
     channel="phone", agent_id.
   - LiveKit JWT token claims verification: sub, iss, video grant (room, roomJoin), metadata.
   - Pinned session creation in SessionRepository.
   - Called number normalization during intake.
4. Tenant isolation & RBAC on /v1/phone-numbers:
   - Cross-tenant penetration: Org B cannot GET, list, PATCH, or DELETE Org A's numbers (404).
   - RBAC enforcement: member role cannot create, patch, or delete (403), but can read (200).
   - Unauthenticated access returns 401 across all endpoints.
5. Backwards compatibility:
   - Legacy /telephony endpoints and string ID support remain fully functional.
"""

import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.security import create_access_token
from backend.app.core.settings import settings
from backend.app.main import app
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.providers.telephony import TwilioSIPProvider, validate_e164_format
from backend.app.modules.sessions.repository import SessionRepository
from backend.app.modules.telephony.repository import TelephonyRepository
from backend.app.modules.telephony.service import (
    is_within_calling_window,
)

# ==============================================================================
# SECTION 1: E.164 Normalization & Validation Edge Cases
# ==============================================================================


@pytest.mark.parametrize(
    ("raw_input", "expected_normalized"),
    [
        # Standard US permutations
        ("+1 (555) 234-5678", "+15552345678"),
        ("+1-555-(234)-(5678)", "+15552345678"),
        (" +1 (555) 019-2831 ", "+15550192831"),
        ("\t+1 (800) 555-0199\n", "+18005550199"),
        ("  +1   555   123   4567  ", "+15551234567"),
        # International country codes
        ("+44 20 7946 0958", "+442079460958"),  # UK
        ("+49 (30) 123456", "+4930123456"),  # Germany
        ("+81 3 1234 5678", "+81312345678"),  # Japan
        ("+33 1 42 68 55 55", "+33142685555"),  # France
        ("+91 (98) 7654-3210", "+919876543210"),  # India
        ("+61 2 9876 5432", "+61298765432"),  # Australia
        # Boundary lengths
        ("+12", "+12"),  # Shortest valid E.164 (2 digits)
        ("+44123456", "+44123456"),
        ("+123456789012345", "+123456789012345"),  # Maximum valid E.164 (15 digits)
    ],
)
def test_e164_normalization_valid_permutations(raw_input: str, expected_normalized: str) -> None:
    """Verify standard and international phone strings normalize cleanly to E.164."""
    provider = TwilioSIPProvider()
    normalized = provider.format_e164(raw_input)
    assert normalized == expected_normalized
    assert provider.validate_e164(normalized) is True
    assert validate_e164_format(normalized) is True


@pytest.mark.parametrize(
    "invalid_raw",
    [
        # Letters and vanity numbers
        "+1-800-FLOWERS",
        "+1555CALLNOW",
        "phone+15551234",
        "+15551234567x101",
        # Missing leading plus
        "15551234567",
        "5551234567",
        "0015551234567",
        "(555) 123-4567",
        # Invalid country codes / leading zero after plus
        "+0123456789",
        "+05551234567",
        # Exceeding ITU-T 15 digit maximum
        "+1234567890123456",  # 16 digits
        "+12345678901234567890",  # 20 digits
        # Too short / empty / whitespace
        "",
        "   ",
        "\t\n ",
        "+",
        "++",
        "+1",  # Only 1 digit (regex requires 2..15 digits)
        # Symbols and non-digit characters
        "+1.555.123.4567",
        "+1#555*1234",
        "+1/555/1234",
        "+1 555 1234?",
        # Malicious payloads
        "+1'; DROP TABLE phone_numbers; --",
        "<script>alert(1)</script>",
        "'+OR+1=1--",
    ],
)
def test_e164_validation_rejections_adversarial(invalid_raw: str) -> None:
    """Verify that all non-conforming or adversarial strings are strictly rejected."""
    provider = TwilioSIPProvider()
    assert provider.validate_e164(invalid_raw) is False
    with pytest.raises(ValueError, match="Invalid E.164"):
        provider.format_e164(invalid_raw)


@pytest.mark.xfail(
    reason="E164_REGEX uses \\d without re.ASCII, matching fullwidth Unicode digits",
    strict=True,
)
def test_e164_non_ascii_unicode_digits_rejected_expected() -> None:
    """E.164 defines decimal digits 0-9. Unicode fullwidth digits should be rejected."""
    provider = TwilioSIPProvider()
    assert provider.validate_e164("+1５５５１２３４５６７") is False


def test_e164_unicode_digits_behavior_empirical_proof() -> None:
    """Empirical proof of vulnerability: E164_REGEX accepts non-ASCII Unicode digits."""
    provider = TwilioSIPProvider()
    # \\d matches unicode fullwidth digits, so this unexpectedly passes validation
    assert provider.validate_e164("+1５５５１２３４５６７") is True
    formatted = provider.format_e164("+1 (５５５) １２３-４５６７")
    assert formatted == "+1５５５１２３４５６７"
    binding = provider.create_sip_trunk_binding(formatted, "sip:inbound.livekit.cloud")
    assert "tk_tw_1５５５１２３４５６７" == binding["trunk_ref"]


@pytest.mark.asyncio
async def test_api_create_phone_number_validation_rejection() -> None:
    """Verify REST API rejects malformed E.164 with HTTP 400 Bad Request."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    token = create_access_token(data={"sub": str(user_id), "org": str(org_id), "role": "admin"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Missing plus
        res_no_plus = await client.post(
            "/v1/phone-numbers",
            headers={"Authorization": f"Bearer {token}"},
            json={"e164": "15551234567", "carrier": "twilio"},
        )
        assert res_no_plus.status_code == 400
        assert "Invalid E.164" in res_no_plus.json()["detail"]

        # 2. Vanity letters
        res_letters = await client.post(
            "/v1/phone-numbers",
            headers={"Authorization": f"Bearer {token}"},
            json={"e164": "+1-800-FLOWERS", "carrier": "twilio"},
        )
        assert res_letters.status_code == 400

        # 3. Leading zero country code
        res_zero = await client.post(
            "/v1/phone-numbers",
            headers={"Authorization": f"Bearer {token}"},
            json={"e164": "+0123456789", "carrier": "twilio"},
        )
        assert res_zero.status_code == 400

        # 4. Length overflow (16 digits)
        res_overflow = await client.post(
            "/v1/phone-numbers",
            headers={"Authorization": f"Bearer {token}"},
            json={"e164": "+1234567890123456", "carrier": "twilio"},
        )
        assert res_overflow.status_code == 400

        # 5. Valid raw string with hyphens/spaces is accepted and normalized
        res_valid = await client.post(
            "/v1/phone-numbers",
            headers={"Authorization": f"Bearer {token}"},
            json={"e164": " +1 (555) 789-0123 ", "carrier": "twilio"},
        )
        assert res_valid.status_code == 201
        assert res_valid.json()["e164"] == "+15557890123"


# ==============================================================================
# SECTION 2: TCPA Calling Window Boundaries (8:00 AM - 8:00 PM)
# ==============================================================================


@pytest.mark.parametrize(
    ("hour", "minute", "second", "microsecond", "expected_permitted"),
    [
        (7, 59, 58, 0, False),  # 2 seconds early
        (7, 59, 59, 0, False),  # 1 second early
        (7, 59, 59, 999999, False),  # 1 microsecond before 8:00 AM
        (8, 0, 0, 0, True),  # Exactly 8:00:00 AM (Start boundary inclusive)
        (8, 0, 1, 0, True),  # 1 second after 8:00 AM
        (12, 0, 0, 0, True),  # Midday (Noon)
        (19, 59, 59, 0, True),  # 1 second before 8:00 PM
        (20, 0, 0, 0, True),  # Exactly 8:00:00 PM (End boundary inclusive)
        (20, 0, 0, 1, False),  # 1 microsecond after 8:00 PM (Blocked)
        (20, 0, 1, 0, False),  # 1 second after 8:00 PM (Blocked)
        (20, 0, 2, 0, False),  # 2 seconds after 8:00 PM
        (23, 59, 59, 0, False),  # Night
        (0, 0, 0, 0, False),  # Midnight
        (4, 30, 0, 0, False),  # Early morning
    ],
)
def test_calling_window_boundary_exact_seconds(
    hour: int, minute: int, second: int, microsecond: int, expected_permitted: bool
) -> None:
    """Verify microsecond and second-level TCPA boundary enforcement (8:00 AM - 8:00 PM)."""
    tz = "America/New_York"
    test_dt = datetime(2026, 10, 24, hour, minute, second, microsecond, tzinfo=ZoneInfo(tz))
    result = is_within_calling_window(now=test_dt, tz_name=tz)
    assert result is expected_permitted, (
        f"Failed at {hour:02d}:{minute:02d}:{second:02d}.{microsecond:06d}: "
        f"expected {expected_permitted}, got {result}"
    )


@pytest.mark.parametrize(
    "tz_name",
    [
        "America/New_York",
        "America/Los_Angeles",
        "America/Chicago",
        "UTC",
        "Asia/Tokyo",
        "Europe/London",
        "Europe/Paris",
        "Australia/Sydney",
    ],
)
def test_calling_window_across_timezones(tz_name: str) -> None:
    """Verify 8am-8pm calling window holds across various international timezones."""
    tz = ZoneInfo(tz_name)

    # 1. Start boundary
    dt_start = datetime(2026, 10, 24, 8, 0, 0, tzinfo=tz)
    assert is_within_calling_window(now=dt_start, tz_name=tz_name) is True

    # 2. Just before start
    dt_before = datetime(2026, 10, 24, 7, 59, 59, tzinfo=tz)
    assert is_within_calling_window(now=dt_before, tz_name=tz_name) is False

    # 3. End boundary
    dt_end = datetime(2026, 10, 24, 20, 0, 0, tzinfo=tz)
    assert is_within_calling_window(now=dt_end, tz_name=tz_name) is True

    # 4. Just after end
    dt_after = datetime(2026, 10, 24, 20, 0, 1, tzinfo=tz)
    assert is_within_calling_window(now=dt_after, tz_name=tz_name) is False


def test_calling_window_simultaneous_utc_cross_zone() -> None:
    """Verify that a single moment in time correctly resolves differently per recipient timezone.

    Moment: 2026-10-24T13:00:00Z (1:00 PM UTC):
    - America/New_York (EDT, UTC-4): 9:00 AM -> Permitted
    - America/Los_Angeles (PDT, UTC-7): 6:00 AM -> Blocked (too early)
    - Asia/Tokyo (JST, UTC+9): 10:00 PM -> Blocked (too late)
    - Europe/London (BST, UTC+1): 2:00 PM -> Permitted
    """
    fixed_utc = datetime(2026, 10, 24, 13, 0, 0, tzinfo=UTC)

    assert is_within_calling_window(now=fixed_utc, tz_name="America/New_York") is True
    assert is_within_calling_window(now=fixed_utc, tz_name="America/Los_Angeles") is False
    assert is_within_calling_window(now=fixed_utc, tz_name="Asia/Tokyo") is False
    assert is_within_calling_window(now=fixed_utc, tz_name="Europe/London") is True


def test_calling_window_invalid_timezone_and_default_handling() -> None:
    """Verify that malformed or non-existent timezone strings fallback gracefully to UTC."""
    # 1. Invalid timezone fallback to UTC
    # 12:00 PM UTC -> Permitted under UTC fallback
    dt_noon_utc = datetime(2026, 10, 24, 12, 0, 0, tzinfo=UTC)
    assert is_within_calling_window(now=dt_noon_utc, tz_name="Fantasy/Atlantis") is True

    # 3:00 AM UTC -> Blocked under UTC fallback
    dt_night_utc = datetime(2026, 10, 24, 3, 0, 0, tzinfo=UTC)
    assert is_within_calling_window(now=dt_night_utc, tz_name="Invalid/Timezone") is False

    # 2. None now argument uses current system time without error
    result = is_within_calling_window(now=None, tz_name="UTC")
    assert isinstance(result, bool)


# ==============================================================================
# SECTION 3: Inbound SIP Dispatch (/internal/sip/inbound)
# ==============================================================================


@pytest.mark.asyncio
async def test_sip_inbound_authentication_security() -> None:
    """Verify /internal/sip/inbound requires valid constant-time X-Internal-Service-Token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "caller_e164": "+15550001111",
            "called_e164": "+15550002222",
            "sip_call_id": "call-sec-test",
        }

        # 1. Missing header
        res_missing = await client.post("/internal/sip/inbound", json=payload)
        assert res_missing.status_code == 401

        # 2. Wrong token
        res_wrong = await client.post(
            "/internal/sip/inbound",
            headers={"X-Internal-Service-Token": "invalid-secret"},
            json=payload,
        )
        assert res_wrong.status_code == 401

        # 3. Empty token
        res_empty = await client.post(
            "/internal/sip/inbound",
            headers={"X-Internal-Service-Token": ""},
            json=payload,
        )
        assert res_empty.status_code == 401


@pytest.mark.asyncio
async def test_sip_inbound_unassigned_number_returns_404() -> None:
    """Verify dialing an existing phone number that has no assigned agent returns 404."""
    telephony_repo = TelephonyRepository()
    org_id = uuid.uuid4()
    e164 = f"+1555{uuid.uuid4().int % 10000000:07d}"

    # Provision number without agent
    await telephony_repo.create_phone_number(
        organization_id=org_id,
        e164=e164,
        carrier="twilio",
        agent_id=None,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/internal/sip/inbound",
            headers={"X-Internal-Service-Token": settings.internal_service_token},
            json={
                "caller_e164": "+15559990001",
                "called_e164": e164,
                "sip_call_id": "call-unassigned-test",
            },
        )
        assert res.status_code == 404
        assert "No agent assigned" in res.json()["detail"]


@pytest.mark.asyncio
async def test_sip_inbound_unknown_number_returns_404() -> None:
    """Verify dialing a completely non-existent phone number returns 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/internal/sip/inbound",
            headers={"X-Internal-Service-Token": settings.internal_service_token},
            json={
                "caller_e164": "+15559990001",
                "called_e164": "+15559999999",
                "sip_call_id": "call-unknown-number",
            },
        )
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_sip_inbound_unversioned_agent_returns_400() -> None:
    """Verify phone number mapped to an agent with no active version returns 400 Bad Request."""
    telephony_repo = TelephonyRepository()
    agent_repo = AgentRepository()
    org_id = uuid.uuid4()

    # Agent created with no published version
    agent = await agent_repo.create_agent(str(org_id), name="Unversioned Agent")
    agent_id = uuid.UUID(agent["id"])

    e164 = f"+1555{uuid.uuid4().int % 10000000:07d}"
    await telephony_repo.create_phone_number(
        organization_id=org_id,
        e164=e164,
        carrier="twilio",
        agent_id=agent_id,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/internal/sip/inbound",
            headers={"X-Internal-Service-Token": settings.internal_service_token},
            json={
                "caller_e164": "+15559990001",
                "called_e164": e164,
                "sip_call_id": "call-unversioned-agent",
            },
        )
        assert res.status_code == 400
        assert "no active version" in res.json()["detail"]


@pytest.mark.asyncio
async def test_sip_inbound_deleted_or_nonexistent_agent_returns_400() -> None:
    """Verify phone number mapped to a deleted/phantom agent ID returns 400."""
    telephony_repo = TelephonyRepository()
    org_id = uuid.uuid4()
    phantom_agent_id = uuid.uuid4()
    e164 = f"+1555{uuid.uuid4().int % 10000000:07d}"

    await telephony_repo.create_phone_number(
        organization_id=org_id,
        e164=e164,
        carrier="twilio",
        agent_id=phantom_agent_id,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/internal/sip/inbound",
            headers={"X-Internal-Service-Token": settings.internal_service_token},
            json={
                "caller_e164": "+15559990001",
                "called_e164": e164,
                "sip_call_id": "call-phantom-agent",
            },
        )
        assert res.status_code == 400
        assert "no active version" in res.json()["detail"]


@pytest.mark.asyncio
async def test_sip_inbound_successful_dispatch_and_jwt_claims() -> None:
    """Verify full successful SIP inbound dispatch, session creation, and LiveKit token claims."""
    telephony_repo = TelephonyRepository()
    agent_repo = AgentRepository()
    session_repo = SessionRepository()
    org_id = uuid.uuid4()

    # 1. Setup active agent with version
    agent = await agent_repo.create_agent(str(org_id), name="Customer Support")
    agent_id = uuid.UUID(agent["id"])
    version = await agent_repo.create_version(
        agent_id=str(agent_id),
        version_no=1,
        system_prompt="You are a helpful phone receptionist.",
        greeting="Thanks for calling Cadence Voice.",
        stt_config={"provider": "deepgram", "model": "nova-2"},
        llm_config={"provider": "openai", "model": "gpt-4o-mini"},
        tts_config={"provider": "cartesia", "voice": "sonic-english"},
    )
    version_id = uuid.UUID(version["id"])
    await agent_repo.set_current_version(str(org_id), str(agent_id), str(version_id))

    # 2. Setup phone number
    e164 = f"+1555{uuid.uuid4().int % 10000000:07d}"
    await telephony_repo.create_phone_number(
        organization_id=org_id,
        e164=e164,
        carrier="twilio",
        agent_id=agent_id,
        trunk_ref="trunk-active-01",
    )

    caller = "+15559876543"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/internal/sip/inbound",
            headers={"X-Internal-Service-Token": settings.internal_service_token},
            json={
                "caller_e164": caller,
                "called_e164": e164,
                "sip_call_id": "sip-call-ok-999",
            },
        )
        assert res.status_code == 200
        data = res.json()

        session_id = data["session_id"]
        room_name = data["room_name"]
        livekit_token = data["livekit_token"]

        assert data["channel"] == "phone"
        assert data["agent_id"] == str(agent_id)
        assert data["livekit_url"] == settings.livekit_url
        assert room_name.startswith("cadence-phone-")

        # 3. Empirically verify LiveKit JWT claims
        decoded = jwt.decode(livekit_token, settings.LIVEKIT_API_SECRET, algorithms=["HS256"])
        assert decoded["sub"] == f"phone-{caller}"
        assert decoded["iss"] == settings.LIVEKIT_API_KEY
        assert decoded["metadata"] == session_id
        assert decoded["video"]["room"] == room_name
        assert decoded["video"]["roomJoin"] is True
        assert decoded["video"]["canPublish"] is True
        assert decoded["video"]["canSubscribe"] is True

        # 4. Verify session record persisted in SessionRepository
        session = await session_repo.get_by_id_internal(session_id)
        assert session is not None
        assert session["channel"] == "phone"
        assert session["organization_id"] == str(org_id)
        assert session["agent_id"] == str(agent_id)
        assert session["agent_version_id"] == str(version_id)
        assert session["room_name"] == room_name


@pytest.mark.asyncio
async def test_sip_inbound_called_number_normalization() -> None:
    """Verify unnormalized called_e164 (with spaces/dashes) resolves to normalized record."""
    telephony_repo = TelephonyRepository()
    agent_repo = AgentRepository()
    org_id = uuid.uuid4()

    agent = await agent_repo.create_agent(str(org_id), name="Dial Normalizer Agent")
    agent_id = uuid.UUID(agent["id"])
    ver = await agent_repo.create_version(
        agent_id=str(agent_id),
        version_no=1,
        system_prompt="Test agent",
        greeting="Hello",
        stt_config={"provider": "deepgram", "model": "nova-2"},
        llm_config={"provider": "openai", "model": "gpt-4o-mini"},
        tts_config={"provider": "cartesia", "voice": "sonic-english"},
    )
    await agent_repo.set_current_version(str(org_id), str(agent_id), ver["id"])

    e164_raw = "+1 (555) 345-6789"
    e164_norm = "+15553456789"
    await telephony_repo.create_phone_number(
        organization_id=org_id,
        e164=e164_norm,
        carrier="twilio",
        agent_id=agent_id,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Call with unnormalized E.164 string
        res = await client.post(
            "/internal/sip/inbound",
            headers={"X-Internal-Service-Token": settings.internal_service_token},
            json={
                "caller_e164": "+15550009999",
                "called_e164": e164_raw,
                "sip_call_id": "call-norm-check",
            },
        )
        assert res.status_code == 200
        assert res.json()["channel"] == "phone"
        assert res.json()["agent_id"] == str(agent_id)


# ==============================================================================
# SECTION 4: Tenant Isolation & RBAC on /v1/phone-numbers
# ==============================================================================


@pytest.mark.asyncio
async def test_cross_tenant_isolation_full_matrix() -> None:
    """Empirically prove Org B cannot access, enumerate, reassign, or delete Org A's numbers."""
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
        # 1. Org A registers a phone number
        e164_a = f"+1555{uuid.uuid4().int % 10000000:07d}"
        res_create = await client.post(
            "/v1/phone-numbers",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"e164": e164_a, "carrier": "twilio"},
        )
        assert res_create.status_code == 201
        phone_a_id = res_create.json()["id"]

        # 2. Org B attempts GET detail -> 404
        res_b_get = await client.get(
            f"/v1/phone-numbers/{phone_a_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert res_b_get.status_code == 404

        # 3. Org B attempts list -> Org A's phone number is NOT returned
        res_b_list = await client.get(
            "/v1/phone-numbers",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert res_b_list.status_code == 200
        org_b_numbers = res_b_list.json()
        assert not any(n["id"] == phone_a_id for n in org_b_numbers)

        # 4. Org B attempts PATCH (reassign agent) -> 404
        malicious_agent_id = str(uuid.uuid4())
        res_b_patch = await client.patch(
            f"/v1/phone-numbers/{phone_a_id}",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"agent_id": malicious_agent_id},
        )
        assert res_b_patch.status_code == 404

        # 5. Org B attempts DELETE -> 404
        res_b_del = await client.delete(
            f"/v1/phone-numbers/{phone_a_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert res_b_del.status_code == 404

        # 6. Verify Org A's phone number is intact and untouched
        res_a_verify = await client.get(
            f"/v1/phone-numbers/{phone_a_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res_a_verify.status_code == 200
        assert res_a_verify.json()["id"] == phone_a_id
        assert res_a_verify.json()["agent_id"] is None


@pytest.mark.asyncio
async def test_rbac_phone_numbers_role_matrix() -> None:
    """Verify RBAC permissions: members cannot mutate phone numbers (403), admins/owners can."""
    org_id = uuid.uuid4()
    admin_token = create_access_token(
        data={"sub": str(uuid.uuid4()), "org": str(org_id), "role": "admin"}
    )
    member_token = create_access_token(
        data={"sub": str(uuid.uuid4()), "org": str(org_id), "role": "member"}
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Admin creates phone number
        e164 = f"+1555{uuid.uuid4().int % 10000000:07d}"
        res_create = await client.post(
            "/v1/phone-numbers",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"e164": e164, "carrier": "twilio"},
        )
        assert res_create.status_code == 201
        phone_id = res_create.json()["id"]

        # 1. Member attempts POST (create) -> 403 Forbidden
        e164_member = f"+1555{uuid.uuid4().int % 10000000:07d}"
        res_member_post = await client.post(
            "/v1/phone-numbers",
            headers={"Authorization": f"Bearer {member_token}"},
            json={"e164": e164_member, "carrier": "twilio"},
        )
        assert res_member_post.status_code == 403

        # 2. Member attempts PATCH -> 403 Forbidden
        res_member_patch = await client.patch(
            f"/v1/phone-numbers/{phone_id}",
            headers={"Authorization": f"Bearer {member_token}"},
            json={"agent_id": str(uuid.uuid4())},
        )
        assert res_member_patch.status_code == 403

        # 3. Member attempts DELETE -> 403 Forbidden
        res_member_delete = await client.delete(
            f"/v1/phone-numbers/{phone_id}",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert res_member_delete.status_code == 403

        # 4. Member CAN read list and detail -> 200 OK
        res_member_list = await client.get(
            "/v1/phone-numbers",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert res_member_list.status_code == 200
        assert any(n["id"] == phone_id for n in res_member_list.json())

        res_member_get = await client.get(
            f"/v1/phone-numbers/{phone_id}",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert res_member_get.status_code == 200
        assert res_member_get.json()["id"] == phone_id


@pytest.mark.asyncio
async def test_phone_numbers_unauthenticated_requests() -> None:
    """Verify that unauthenticated requests to /v1/phone-numbers are rejected with 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # No header
        assert (await client.get("/v1/phone-numbers")).status_code == 401
        assert (await client.get(f"/v1/phone-numbers/{uuid.uuid4()}")).status_code == 401
        assert (
            await client.post("/v1/phone-numbers", json={"e164": "+15551234567"})
        ).status_code == 401
        assert (await client.patch(f"/v1/phone-numbers/{uuid.uuid4()}", json={})).status_code == 401
        assert (await client.delete(f"/v1/phone-numbers/{uuid.uuid4()}")).status_code == 401

        # Malformed bearer token
        assert (
            await client.get(
                "/v1/phone-numbers", headers={"Authorization": "Bearer not-a-valid-jwt"}
            )
        ).status_code == 401


# ==============================================================================
# SECTION 5: Backwards Compatibility & Legacy Endpoints
# ==============================================================================


@pytest.mark.asyncio
async def test_legacy_telephony_routes_and_string_ids() -> None:
    """Verify legacy /telephony routes and mock string IDs continue to function smoothly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. GET /telephony/numbers with organization_id query param
        res_list = await client.get("/telephony/numbers?organization_id=org-legacy-1")
        assert res_list.status_code == 200
        assert isinstance(res_list.json(), list)

        # 2. GET /telephony/numbers/{id}
        res_detail = await client.get("/telephony/numbers/pn-mock-1?organization_id=org-legacy-1")
        assert res_detail.status_code == 200
        assert res_detail.json()["id"] == "pn-mock-1"

        # 3. POST /telephony/numbers/{id}/assign
        new_agent = "agent-legacy-assigned"
        res_assign = await client.post(
            "/telephony/numbers/pn-mock-1/assign?organization_id=org-legacy-1",
            json={"agent_id": new_agent},
        )
        assert res_assign.status_code == 200
        assert res_assign.json()["agent_id"] == new_agent
