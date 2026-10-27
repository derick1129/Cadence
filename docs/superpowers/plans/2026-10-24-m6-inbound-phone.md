# Milestone M6: Inbound Phone & Telephony Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable inbound PSTN and SIP phone calls to reach configured voice agents, with database persistence, carrier/trunk abstractions, calling window compliance, internal dispatch gateways, and authenticated number management APIs.

**Architecture:** Layered modular monolith with strict domain boundaries. The `telephony` module owns `phone_numbers` table mapping E.164 numbers to `organizations` and `agents`. A `TelephonyProvider` abstraction decouples carrier operations (Twilio/Telnyx). When LiveKit SIP receives an inbound telephone call, it dispatches an internal webhook to `/internal/sip/inbound`, which validates `X-Internal-Service-Token`, verifies calling-window rules, creates a `phone` channel session pinned to the agent's current version, and issues a LiveKit SIP participant token. Customers manage and route numbers via authenticated `/v1/phone-numbers` REST endpoints.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (asyncio, asyncpg), Alembic, Pydantic v2, Pytest, Import-Linter.

## Global Constraints

- Never commit directly to `main`; work on short-lived feature branch `feat/m6-inbound-phone`.
- Every Python file must be fully type-annotated (`mypy` strict mode without `Any` unless justified).
- Standard JSON error shape for API: `{"error": {"code": "...", "message": "...", "details": ...}}`.
- Never place real phone calls from tests or scripts; use mock providers and test numbers.
- Repositories refuse to run tenant queries without an explicit `organization_id`.
- Outbound calling window rule (8am - 8pm in recipient timezone) must be enforced.
- No PII (phone numbers, full caller audio paths, raw transcripts) logged at `INFO` level or above.
- Quality commands must pass before commit:
  - `ruff check . && ruff format --check .`
  - `mypy backend worker`
  - `pytest -q`
  - `lint-imports`

---

### Task 1: Database ORM Models (`PhoneNumber`) & Migration `0006_telephony`

**Files:**
- Create: `backend/app/modules/telephony/models.py`
- Create: `backend/app/migrations/versions/0006_telephony.py`
- Modify: `backend/app/modules/telephony/__init__.py`
- Modify: `backend/app/migrations/env.py`
- Test: `backend/tests/test_telephony_models.py`

**Interfaces:**
- Consumes: `Base`, `TimestampMixin` from `backend.app.core.base`.
- Produces:
  - `PhoneNumber`: `id` (UUID), `organization_id` (UUID FK to organizations.id), `e164` (VARCHAR(32), unique, indexed), `carrier` (VARCHAR(32)), `agent_id` (UUID FK to agents.id, nullable), `trunk_ref` (VARCHAR(255), nullable), `created_at`, `updated_at`.

- [ ] **Step 1: Write the failing test for PhoneNumber model**

Create `backend/tests/test_telephony_models.py`:
```python
"""Tests for PhoneNumber SQLAlchemy ORM model."""

import uuid

from backend.app.modules.telephony.models import PhoneNumber


def test_phone_number_model_instantiation() -> None:
    """Verify PhoneNumber model fields, organization ownership, and agent routing."""
    org_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    number = PhoneNumber(
        organization_id=org_id,
        e164="+15551234567",
        carrier="twilio",
        agent_id=agent_id,
        trunk_ref="trunk-tw-test-01",
    )
    assert number.organization_id == org_id
    assert number.e164 == "+15551234567"
    assert number.carrier == "twilio"
    assert number.agent_id == agent_id
    assert number.trunk_ref == "trunk-tw-test-01"
    assert isinstance(number.id, uuid.UUID)


def test_phone_number_optional_routing() -> None:
    """Verify PhoneNumber can exist unassigned without an agent."""
    org_id = uuid.uuid4()
    number = PhoneNumber(
        organization_id=org_id,
        e164="+15559876543",
        carrier="telnyx",
    )
    assert number.organization_id == org_id
    assert number.agent_id is None
    assert number.trunk_ref is None
    assert isinstance(number.id, uuid.UUID)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_telephony_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.modules.telephony.models'`

- [ ] **Step 3: Implement PhoneNumber model**

Create `backend/app/modules/telephony/models.py`:
```python
"""PhoneNumber SQLAlchemy model."""

import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.base import Base, TimestampMixin


class PhoneNumber(Base, TimestampMixin):
    """Inbound and outbound telephone number configuration."""

    __tablename__ = "phone_numbers"
    __table_args__ = (
        Index("ix_phone_numbers_organization_id", "organization_id"),
        Index("ix_phone_numbers_e164", "e164", unique=True),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    e164: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    carrier: Mapped[str] = mapped_column(String(32), nullable=False, default="twilio")
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    trunk_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

Export in `backend/app/modules/telephony/__init__.py`:
```python
"""Telephony domain module."""

from backend.app.modules.telephony.models import PhoneNumber
from backend.app.modules.telephony.repository import TelephonyRepository
from backend.app.modules.telephony.router import router
from backend.app.modules.telephony.schemas import (
    PhoneNumberAssign,
    PhoneNumberCreate,
    PhoneNumberResponse,
    PhoneNumberUpdate,
)
from backend.app.modules.telephony.service import TelephonyService

__all__ = [
    "PhoneNumber",
    "PhoneNumberAssign",
    "PhoneNumberCreate",
    "PhoneNumberResponse",
    "PhoneNumberUpdate",
    "TelephonyRepository",
    "TelephonyService",
    "router",
]
```

Import in `backend/app/migrations/env.py`:
```python
from backend.app.modules.telephony.models import PhoneNumber  # noqa: F401
```

- [ ] **Step 4: Create migration `0006_telephony.py`**

Create `backend/app/migrations/versions/0006_telephony.py`:
```python
"""telephony

Revision ID: 0006_telephony
Revises: 0005_tools_and_audit
Create Date: 2026-10-24 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_telephony"
down_revision: str | None = "0005_tools_and_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "phone_numbers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("e164", sa.String(length=32), nullable=False),
        sa.Column("carrier", sa.String(length=32), nullable=False, server_default="twilio"),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("trunk_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("e164", name="uq_phone_numbers_e164"),
    )
    op.create_index("ix_phone_numbers_organization_id", "phone_numbers", ["organization_id"])
    op.create_index("ix_phone_numbers_e164", "phone_numbers", ["e164"], unique=True)


def downgrade() -> None:
    op.drop_table("phone_numbers")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/bin/pytest backend/tests/test_telephony_models.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/telephony/models.py backend/app/modules/telephony/__init__.py backend/app/migrations/env.py backend/app/migrations/versions/0006_telephony.py backend/tests/test_telephony_models.py
git commit -m "feat(telephony): add phone_number model with alembic migration"
```

---

### Task 2: Telephony Provider Abstraction & Twilio/SIP Provider (`backend/app/modules/providers/telephony.py`)

**Files:**
- Create: `backend/app/modules/providers/telephony.py`
- Modify: `backend/app/modules/providers/__init__.py`
- Test: `backend/tests/test_telephony_provider.py`

**Interfaces:**
- Consumes: None (Protocol definition).
- Produces:
  - `TelephonyProvider` Protocol: `format_e164(raw: str) -> str`, `validate_e164(number: str) -> bool`, `create_sip_trunk_binding(e164: str, livekit_sip_uri: str) -> dict[str, str]`.
  - `TwilioSIPProvider`: Production implementation with test number formatting and SIP URI binding generation.

- [ ] **Step 1: Write the failing test for TelephonyProvider**

Create `backend/tests/test_telephony_provider.py`:
```python
"""Tests for TelephonyProvider interface and TwilioSIPProvider implementation."""

import pytest

from backend.app.modules.providers.telephony import TwilioSIPProvider, validate_e164_format


def test_validate_e164_format() -> None:
    """Verify strict E.164 regex and international formatting validation."""
    assert validate_e164_format("+15551234567") is True
    assert validate_e164_format("+442071838750") is True
    assert validate_e164_format("+919876543210") is True

    # Invalid patterns
    assert validate_e164_format("15551234567") is False  # missing plus
    assert validate_e164_format("+1(555)123-4567") is False  # special chars
    assert validate_e164_format("+0123456") is False  # invalid country code
    assert validate_e164_format("not-a-number") is False


def test_twilio_sip_provider_formatting() -> None:
    """Verify Twilio provider strips whitespaces and normalizes valid numbers."""
    provider = TwilioSIPProvider(account_sid="AC_test", auth_token="token_test")
    assert provider.format_e164(" +1 555 123 4567 ") == "+15551234567"

    with pytest.raises(ValueError, match="Invalid E.164 phone number format"):
        provider.format_e164("invalid")


def test_twilio_sip_provider_trunk_binding() -> None:
    """Verify Twilio SIP trunk URI binding synthesis for LiveKit SIP inbound routing."""
    provider = TwilioSIPProvider(account_sid="AC_test", auth_token="token_test")
    binding = provider.create_sip_trunk_binding(
        e164="+15551234567",
        livekit_sip_uri="sip:inbound.livekit.cloud;transport=tls",
    )
    assert binding["e164"] == "+15551234567"
    assert binding["carrier"] == "twilio"
    assert "trunk_ref" in binding
    assert binding["target_sip_uri"] == "sip:inbound.livekit.cloud;transport=tls"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_telephony_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.modules.providers.telephony'`

- [ ] **Step 3: Implement TelephonyProvider and TwilioSIPProvider**

Create `backend/app/modules/providers/telephony.py`:
```python
"""Telephony provider protocol and Twilio SIP implementation."""

import re
from typing import Any, Protocol

E164_REGEX = re.compile(r"^\+[1-9]\d{1,14}$")


def validate_e164_format(number: str) -> bool:
    """Validate that a string conforms to ITU-T E.164 phone number formatting."""
    return bool(E164_REGEX.match(number.strip()))


class TelephonyProvider(Protocol):
    """Protocol defining telephony carrier and SIP trunk operations."""

    def format_e164(self, raw: str) -> str:
        """Normalize raw user string into standard E.164."""
        ...

    def validate_e164(self, number: str) -> bool:
        """Return True if number is a valid E.164 string."""
        ...

    def create_sip_trunk_binding(
        self, e164: str, livekit_sip_uri: str
    ) -> dict[str, str]:
        """Configure SIP forwarding on the carrier towards LiveKit SIP ingress."""
        ...


class TwilioSIPProvider:
    """Twilio programmable SIP trunking provider implementation."""

    def __init__(self, account_sid: str = "", auth_token: str = "") -> None:
        self.account_sid = account_sid
        self.auth_token = auth_token

    def validate_e164(self, number: str) -> bool:
        """Validate E.164 formatting."""
        return validate_e164_format(number)

    def format_e164(self, raw: str) -> str:
        """Strip spaces, hyphens, parentheses and enforce leading plus."""
        cleaned = re.sub(r"[\s\-\(\)]", "", raw)
        if not self.validate_e164(cleaned):
            raise ValueError(f"Invalid E.164 phone number format: '{raw}'")
        return cleaned

    def create_sip_trunk_binding(
        self, e164: str, livekit_sip_uri: str
    ) -> dict[str, str]:
        """Generate mock/active carrier trunk reference binding for inbound SIP calls."""
        normalized = self.format_e164(e164)
        trunk_ref = f"tk_tw_{normalized.replace('+', '')}"
        return {
            "e164": normalized,
            "carrier": "twilio",
            "trunk_ref": trunk_ref,
            "target_sip_uri": livekit_sip_uri,
        }
```

Export in `backend/app/modules/providers/__init__.py`:
```python
from backend.app.modules.providers.telephony import (
    TelephonyProvider,
    TwilioSIPProvider,
    validate_e164_format,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest backend/tests/test_telephony_provider.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/providers/telephony.py backend/app/modules/providers/__init__.py backend/tests/test_telephony_provider.py
git commit -m "feat(providers): add telephony provider protocol and twilio sip provider"
```

---

### Task 3: Real Database Repository for Telephony (`backend/app/modules/telephony/repository.py`)

**Files:**
- Modify: `backend/app/modules/telephony/repository.py`
- Test: `backend/tests/test_telephony_repository.py`

**Interfaces:**
- Consumes: `PhoneNumber` model, `AsyncSession` from SQLAlchemy.
- Produces:
  - `TelephonyRepository.list_by_org(organization_id)`
  - `TelephonyRepository.get_by_id(organization_id, phone_number_id)`
  - `TelephonyRepository.get_by_e164(e164)`
  - `TelephonyRepository.create_phone_number(organization_id, e164, carrier, agent_id, trunk_ref)`
  - `TelephonyRepository.assign_agent(organization_id, phone_number_id, agent_id)`
  - `TelephonyRepository.delete_phone_number(organization_id, phone_number_id)`

- [ ] **Step 1: Write the failing test for TelephonyRepository**

Create `backend/tests/test_telephony_repository.py`:
```python
"""Tests for TelephonyRepository database queries and tenant isolation."""

import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import AsyncSessionLocal
from backend.app.modules.telephony.models import PhoneNumber
from backend.app.modules.telephony.repository import TelephonyRepository


@pytest.mark.asyncio
async def test_telephony_repository_lifecycle() -> None:
    """Verify create, get, assign, list, and delete operations."""
    async with AsyncSessionLocal() as session:
        repo = TelephonyRepository(session)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_telephony_repository.py -v`
Expected: FAIL (AttributeError or methods missing on stub).

- [ ] **Step 3: Implement real database TelephonyRepository**

Modify `backend/app/modules/telephony/repository.py`:
```python
"""Telephony repository for database persistence."""

import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.telephony.models import PhoneNumber


class TelephonyRepository:
    """Repository handling database operations for phone numbers and carrier routing."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_org(self, organization_id: uuid.UUID) -> Sequence[PhoneNumber]:
        """List all phone numbers owned by an organization."""
        query = (
            select(PhoneNumber)
            .where(PhoneNumber.organization_id == organization_id)
            .order_by(PhoneNumber.created_at.desc())
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_id(
        self, organization_id: uuid.UUID, phone_number_id: uuid.UUID
    ) -> PhoneNumber | None:
        """Fetch phone number details strictly scoped to organization."""
        query = select(PhoneNumber).where(
            PhoneNumber.id == phone_number_id,
            PhoneNumber.organization_id == organization_id,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_e164(self, e164: str) -> PhoneNumber | None:
        """Find a phone number by its E.164 string for SIP intake routing."""
        query = select(PhoneNumber).where(PhoneNumber.e164 == e164)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_phone_number(
        self,
        organization_id: uuid.UUID,
        e164: str,
        carrier: str = "twilio",
        agent_id: uuid.UUID | None = None,
        trunk_ref: str | None = None,
    ) -> PhoneNumber:
        """Create and persist a new phone number record."""
        number = PhoneNumber(
            organization_id=organization_id,
            e164=e164,
            carrier=carrier,
            agent_id=agent_id,
            trunk_ref=trunk_ref,
        )
        self.session.add(number)
        await self.session.commit()
        await self.session.refresh(number)
        return number

    async def assign_agent(
        self,
        organization_id: uuid.UUID,
        phone_number_id: uuid.UUID,
        agent_id: uuid.UUID | None,
    ) -> PhoneNumber | None:
        """Assign or unassign an agent for a phone number."""
        number = await self.get_by_id(organization_id, phone_number_id)
        if not number:
            return None
        number.agent_id = agent_id
        await self.session.commit()
        await self.session.refresh(number)
        return number

    async def delete_phone_number(
        self, organization_id: uuid.UUID, phone_number_id: uuid.UUID
    ) -> bool:
        """Delete a phone number record belonging to the organization."""
        query = delete(PhoneNumber).where(
            PhoneNumber.id == phone_number_id,
            PhoneNumber.organization_id == organization_id,
        )
        result = await self.session.execute(query)
        await self.session.commit()
        return bool(result.rowcount and result.rowcount > 0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest backend/tests/test_telephony_repository.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/telephony/repository.py backend/tests/test_telephony_repository.py
git commit -m "feat(telephony): implement database persistence in telephony repository"
```

---

### Task 4: Telephony Service, Schemas & Calling Window Compliance (`backend/app/modules/telephony/service.py`)

**Files:**
- Modify: `backend/app/modules/telephony/schemas.py`
- Modify: `backend/app/modules/telephony/service.py`
- Test: `backend/tests/test_telephony_service.py`

**Interfaces:**
- Consumes: `TelephonyRepository`, `TwilioSIPProvider`, `AgentRepository`.
- Produces:
  - `PhoneNumberCreate`, `PhoneNumberUpdate`, `PhoneNumberResponse`.
  - `TelephonyService`: `is_within_calling_window(now, tz_name) -> bool`, `create_number(...)`, `assign_agent(...)`.

- [ ] **Step 1: Write the failing test for TelephonyService**

Create `backend/tests/test_telephony_service.py`:
```python
"""Tests for TelephonyService business logic, E.164 normalization, and calling windows."""

import datetime
from datetime import UTC, datetime, time
import uuid
import pytest
from zoneinfo import ZoneInfo

from backend.app.modules.telephony.schemas import PhoneNumberCreate
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
async def test_telephony_service_create_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify service normalizes E.164 string through telephony provider."""
    service = TelephonyService(repository=None)  # type: ignore[arg-type]

    # Malformed E.164 raises ValueError
    with pytest.raises(ValueError, match="Invalid E.164"):
        service.normalize_number("12345")

    assert service.normalize_number(" +1 (555) 019-2831 ") == "+15550192831"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_telephony_service.py -v`
Expected: FAIL with missing methods/attributes.

- [ ] **Step 3: Implement TelephonyService and update Schemas**

Update `backend/app/modules/telephony/schemas.py`:
```python
"""Telephony module schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PhoneNumberCreate(BaseModel):
    """Payload to register or provision a phone number."""

    e164: str = Field(..., description="E.164 formatted telephone number")
    carrier: str = Field("twilio", description="Carrier name (e.g. twilio, telnyx)")
    agent_id: uuid.UUID | None = None
    trunk_ref: str | None = None


class PhoneNumberUpdate(BaseModel):
    """Payload to update routing or trunk configuration."""

    agent_id: uuid.UUID | None = None
    trunk_ref: str | None = None


class PhoneNumberAssign(BaseModel):
    """Payload to assign or unassign a phone number to an agent."""

    agent_id: uuid.UUID | None = None


class PhoneNumberResponse(BaseModel):
    """Phone number configuration and routing details."""

    id: uuid.UUID
    organization_id: uuid.UUID
    e164: str
    carrier: str
    agent_id: uuid.UUID | None = None
    trunk_ref: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

Update `backend/app/modules/telephony/service.py`:
```python
"""Telephony service containing business logic and compliance checks."""

import datetime
from datetime import UTC, datetime, time
import uuid
from zoneinfo import ZoneInfo

from backend.app.modules.providers.telephony import TwilioSIPProvider
from backend.app.modules.telephony.models import PhoneNumber
from backend.app.modules.telephony.repository import TelephonyRepository
from backend.app.modules.telephony.schemas import (
    PhoneNumberAssign,
    PhoneNumberCreate,
    PhoneNumberResponse,
    PhoneNumberUpdate,
)


def is_within_calling_window(
    now: datetime | None = None, tz_name: str = "America/New_York"
) -> bool:
    """Enforce TCPA calling window: strictly 8:00 AM to 8:00 PM local recipient time."""
    current = now or datetime.now(UTC)
    try:
        local_time = current.astimezone(ZoneInfo(tz_name))
    except Exception:
        local_time = current.astimezone(ZoneInfo("UTC"))

    start = time(8, 0, 0)
    end = time(20, 0, 0)
    return start <= local_time.time() <= end


class TelephonyService:
    """Business logic for telephony numbers, carrier provisioning, and agent routing."""

    def __init__(
        self,
        repository: TelephonyRepository,
        provider: TwilioSIPProvider | None = None,
    ) -> None:
        self.repository = repository
        self.provider = provider or TwilioSIPProvider()

    def normalize_number(self, raw_number: str) -> str:
        """Normalize raw string to verified E.164 format."""
        return self.provider.format_e164(raw_number)

    async def list_phone_numbers(
        self, organization_id: uuid.UUID
    ) -> list[PhoneNumberResponse]:
        """List all phone numbers configured for an organization."""
        numbers = await self.repository.list_by_org(organization_id)
        return [PhoneNumberResponse.model_validate(n) for n in numbers]

    async def get_phone_number(
        self, organization_id: uuid.UUID, phone_number_id: uuid.UUID
    ) -> PhoneNumberResponse | None:
        """Fetch details for a specific phone number."""
        number = await self.repository.get_by_id(organization_id, phone_number_id)
        if not number:
            return None
        return PhoneNumberResponse.model_validate(number)

    async def get_by_e164(self, e164: str) -> PhoneNumber | None:
        """Look up phone number routing entity by normalized E.164 string."""
        normalized = self.normalize_number(e164)
        return await self.repository.get_by_e164(normalized)

    async def create_phone_number(
        self, organization_id: uuid.UUID, payload: PhoneNumberCreate
    ) -> PhoneNumberResponse:
        """Register a new telephone number for an organization."""
        normalized = self.normalize_number(payload.e164)
        trunk_ref = payload.trunk_ref
        if not trunk_ref:
            binding = self.provider.create_sip_trunk_binding(
                normalized, livekit_sip_uri="sip:inbound.livekit.cloud;transport=tls"
            )
            trunk_ref = binding.get("trunk_ref")

        number = await self.repository.create_phone_number(
            organization_id=organization_id,
            e164=normalized,
            carrier=payload.carrier,
            agent_id=payload.agent_id,
            trunk_ref=trunk_ref,
        )
        return PhoneNumberResponse.model_validate(number)

    async def assign_agent(
        self,
        organization_id: uuid.UUID,
        phone_number_id: uuid.UUID,
        agent_id: uuid.UUID | None,
    ) -> PhoneNumberResponse | None:
        """Assign or unassign an agent to a phone number."""
        updated = await self.repository.assign_agent(
            organization_id, phone_number_id, agent_id
        )
        if not updated:
            return None
        return PhoneNumberResponse.model_validate(updated)

    async def delete_phone_number(
        self, organization_id: uuid.UUID, phone_number_id: uuid.UUID
    ) -> bool:
        """Remove a phone number registration."""
        return await self.repository.delete_phone_number(organization_id, phone_number_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest backend/tests/test_telephony_service.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/telephony/schemas.py backend/app/modules/telephony/service.py backend/tests/test_telephony_service.py
git commit -m "feat(telephony): implement service logic, calling window checks, and schemas"
```

---

### Task 5: Inbound SIP Gateway Endpoint (`/internal/sip/inbound`)

**Files:**
- Modify: `backend/app/modules/internal/router.py`
- Modify: `backend/app/modules/internal/schemas.py`
- Test: `backend/tests/test_internal_sip_inbound.py`

**Interfaces:**
- Consumes: `TelephonyService`, `AgentRepository`, `SessionRepository`, `generate_livekit_token`.
- Produces:
  - `POST /internal/sip/inbound`: Receives `{ "caller_e164": "...", "called_e164": "...", "sip_call_id": "..." }`.
  - Returns LiveKit room name, participant token, session ID, and agent routing instructions.

- [ ] **Step 1: Write the failing test for Inbound SIP gateway**

Create `backend/tests/test_internal_sip_inbound.py`:
```python
"""Tests for /internal/sip/inbound SIP dispatch gateway endpoint."""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.database import AsyncSessionLocal
from backend.app.core.settings import settings
from backend.app.main import app
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.telephony.repository import TelephonyRepository


@pytest.mark.asyncio
async def test_internal_sip_inbound_flow() -> None:
    """Verify inbound SIP dispatch creates a phone session and returns LiveKit credentials."""
    async with AsyncSessionLocal() as session:
        telephony_repo = TelephonyRepository(session)
        agent_repo = AgentRepository(session)
        org_id = uuid.uuid4()

        # Create agent with version
        agent = await agent_repo.create_agent(org_id, name="Phone Support Agent")
        version = await agent_repo.create_agent_version(
            agent_id=agent.id,
            system_prompt="You are a phone receptionist.",
            greeting="Hello, thanks for calling.",
            stt_config={"provider": "deepgram", "model": "nova-2"},
            llm_config={"provider": "openai", "model": "gpt-4o-mini"},
            tts_config={"provider": "cartesia", "voice": "sonic-english"},
            version_no=1,
        )
        await agent_repo.set_current_version(org_id, agent.id, version.id)

        # Register phone number mapped to agent
        e164 = f"+1555{uuid.uuid4().int % 10000000:07d}"
        await telephony_repo.create_phone_number(
            organization_id=org_id,
            e164=e164,
            carrier="twilio",
            agent_id=agent.id,
            trunk_ref="trunk-inbound-test",
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Reject without valid internal token
        res_unauth = await client.post(
            "/internal/sip/inbound",
            headers={"X-Internal-Service-Token": "bad-token"},
            json={
                "caller_e164": "+15550009999",
                "called_e164": e164,
                "sip_call_id": "call-sip-xyz-123",
            },
        )
        assert res_unauth.status_code == 401

        # 2. Dispatch successfully with valid token
        res = await client.post(
            "/internal/sip/inbound",
            headers={"X-Internal-Service-Token": settings.internal_service_token},
            json={
                "caller_e164": "+15550009999",
                "called_e164": e164,
                "sip_call_id": "call-sip-xyz-123",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert "room_name" in data
        assert "livekit_token" in data
        assert "session_id" in data
        assert data["channel"] == "phone"
        assert data["agent_id"] == str(agent.id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_internal_sip_inbound.py -v`
Expected: FAIL with 404 (Route `/internal/sip/inbound` not found).

- [ ] **Step 3: Implement Inbound SIP Gateway endpoint**

Add schemas to `backend/app/modules/internal/schemas.py`:
```python
class SipInboundRequest(BaseModel):
    """Payload sent by LiveKit SIP Dispatch on incoming carrier call."""

    caller_e164: str
    called_e164: str
    sip_call_id: str


class SipInboundResponse(BaseModel):
    """Routing instructions and LiveKit token for inbound phone session."""

    session_id: str
    room_name: str
    livekit_token: str
    livekit_url: str
    channel: str = "phone"
    agent_id: str
```

Add endpoint in `backend/app/modules/internal/router.py`:
```python
from backend.app.core.livekit import generate_livekit_token
from backend.app.modules.internal.schemas import SipInboundRequest, SipInboundResponse
from backend.app.modules.telephony.repository import TelephonyRepository
from backend.app.modules.telephony.service import TelephonyService


@router.post("/sip/inbound", response_model=SipInboundResponse)
async def handle_sip_inbound(
    request: SipInboundRequest,
    authenticated: None = Depends(verify_internal_token),
    db: AsyncSession = Depends(get_db_session),
) -> SipInboundResponse:
    """LiveKit SIP inbound call intake. Maps dialed E.164 to agent and initiates session."""
    telephony_repo = TelephonyRepository(db)
    telephony_service = TelephonyService(telephony_repo)
    agent_repo = AgentRepository(db)
    session_repo = SessionRepository(db)

    phone_record = await telephony_service.get_by_e164(request.called_e164)
    if not phone_record or not phone_record.agent_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No agent assigned to this phone number",
        )

    agent = await agent_repo.get_agent(phone_record.organization_id, phone_record.agent_id)
    if not agent or not agent.current_version_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configured agent has no active version",
        )

    session_id = uuid.uuid4()
    room_name = f"cadence-phone-{session_id}"

    # Create phone session
    new_session = await session_repo.create_session(
        session_id=session_id,
        organization_id=phone_record.organization_id,
        agent_id=agent.id,
        agent_version_id=agent.current_version_id,
        room_name=room_name,
        channel="phone",
    )

    livekit_token = generate_livekit_token(
        room_name=room_name,
        participant_identity=f"phone-{request.caller_e164}",
        participant_name=request.caller_e164,
    )

    return SipInboundResponse(
        session_id=str(new_session.id),
        room_name=room_name,
        livekit_token=livekit_token,
        livekit_url=settings.livekit_url,
        channel="phone",
        agent_id=str(agent.id),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest backend/tests/test_internal_sip_inbound.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/internal/router.py backend/app/modules/internal/schemas.py backend/tests/test_internal_sip_inbound.py
git commit -m "feat(internal): add /internal/sip/inbound gateway for livekit telephony dispatch"
```

---

### Task 6: Authenticated Customer Telephony REST API & Cross-Tenant Isolation Tests

**Files:**
- Modify: `backend/app/modules/telephony/router.py`
- Test: `backend/tests/test_telephony_api.py`
- Test: `backend/tests/test_telephony_cross_tenant.py`

**Interfaces:**
- Consumes: `get_current_user`, `require_role`, `get_db_session`.
- Produces:
  - `POST /v1/phone-numbers`: Provision/register number.
  - `GET /v1/phone-numbers`: List numbers.
  - `GET /v1/phone-numbers/{id}`: Detail.
  - `PATCH /v1/phone-numbers/{id}`: Reassign agent.
  - `DELETE /v1/phone-numbers/{id}`: Release number.

- [ ] **Step 1: Write the failing test for Telephony REST API and Cross-Tenant isolation**

Create `backend/tests/test_telephony_api.py`:
```python
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
```

Create `backend/tests/test_telephony_cross_tenant.py`:
```python
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
    token_a = create_access_token(data={"sub": str(uuid.uuid4()), "org": str(org_a), "role": "admin"})
    token_b = create_access_token(data={"sub": str(uuid.uuid4()), "org": str(org_b), "role": "admin"})

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/pytest backend/tests/test_telephony_api.py backend/tests/test_telephony_cross_tenant.py -v`
Expected: FAIL with 404/401 (endpoints not wired under `/v1/phone-numbers`).

- [ ] **Step 3: Update Telephony Router with Auth & Tenancy**

Modify `backend/app/modules/telephony/router.py`:
```python
"""Telephony router providing authenticated customer endpoints for phone numbers."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db_session
from backend.app.core.security import TokenData, get_current_user, require_role
from backend.app.modules.telephony.repository import TelephonyRepository
from backend.app.modules.telephony.schemas import (
    PhoneNumberCreate,
    PhoneNumberResponse,
    PhoneNumberUpdate,
)
from backend.app.modules.telephony.service import TelephonyService

router = APIRouter(prefix="/v1/phone-numbers", tags=["telephony"])


def get_telephony_service(
    session: AsyncSession = Depends(get_db_session),
) -> TelephonyService:
    """Dependency provider injecting database session into TelephonyService."""
    repo = TelephonyRepository(session)
    return TelephonyService(repo)


@router.post("", response_model=PhoneNumberResponse, status_code=status.HTTP_201_CREATED)
async def create_phone_number(
    payload: PhoneNumberCreate,
    current_user: TokenData = Depends(require_role(["owner", "admin"])),
    service: TelephonyService = Depends(get_telephony_service),
) -> PhoneNumberResponse:
    """Register or provision a new phone number for the organization."""
    try:
        return await service.create_phone_number(current_user.organization_id, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=list[PhoneNumberResponse])
async def list_phone_numbers(
    current_user: TokenData = Depends(get_current_user),
    service: TelephonyService = Depends(get_telephony_service),
) -> list[PhoneNumberResponse]:
    """List all phone numbers owned by the current organization."""
    return await service.list_phone_numbers(current_user.organization_id)


@router.get("/{phone_number_id}", response_model=PhoneNumberResponse)
async def get_phone_number(
    phone_number_id: uuid.UUID,
    current_user: TokenData = Depends(get_current_user),
    service: TelephonyService = Depends(get_telephony_service),
) -> PhoneNumberResponse:
    """Retrieve details for a specific phone number."""
    number = await service.get_phone_number(current_user.organization_id, phone_number_id)
    if not number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found",
        )
    return number


@router.patch("/{phone_number_id}", response_model=PhoneNumberResponse)
async def update_phone_number(
    phone_number_id: uuid.UUID,
    payload: PhoneNumberUpdate,
    current_user: TokenData = Depends(require_role(["owner", "admin"])),
    service: TelephonyService = Depends(get_telephony_service),
) -> PhoneNumberResponse:
    """Assign or reassign an agent to a phone number."""
    number = await service.assign_agent(
        organization_id=current_user.organization_id,
        phone_number_id=phone_number_id,
        agent_id=payload.agent_id,
    )
    if not number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found",
        )
    return number


@router.delete("/{phone_number_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_phone_number(
    phone_number_id: uuid.UUID,
    current_user: TokenData = Depends(require_role(["owner", "admin"])),
    service: TelephonyService = Depends(get_telephony_service),
) -> None:
    """Release a phone number from the organization."""
    deleted = await service.delete_phone_number(current_user.organization_id, phone_number_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found",
        )
```

Also mount router at `/v1/phone-numbers` in `backend/app/main.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/pytest backend/tests/test_telephony_api.py backend/tests/test_telephony_cross_tenant.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run full verification suite**

Run: `./.venv/bin/ruff check . && ./.venv/bin/ruff format --check . && ./.venv/bin/mypy backend worker && ./.venv/bin/pytest -q && ./.venv/bin/lint-imports`
Expected: All clean, 0 errors, all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/telephony/router.py backend/app/main.py backend/tests/test_telephony_api.py backend/tests/test_telephony_cross_tenant.py
git commit -m "feat(telephony): add authenticated customer phone numbers api with cross-tenant isolation"
```
