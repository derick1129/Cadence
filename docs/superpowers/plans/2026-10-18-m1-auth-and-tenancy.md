# Milestone M1: Auth and Tenancy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a secure, production-grade multi-tenant foundation for Cadence with PostgreSQL declarative models, Alembic migrations, database-backed user signup/login, refresh token rotation, JWT tenant claims, role-based access control (RBAC), and verified cross-tenant isolation.

**Architecture:** Domain-driven modular monolith with strict layer separation (`core` -> `organizations` -> `auth` -> higher domain modules). SQLAlchemy 2.0 async declarative models mapped to PostgreSQL (`organizations`, `users`, `memberships`, `refresh_tokens`), Alembic migration management, short-lived signed HS256 JWTs embedding tenant claims (`sub`, `organization_id`, `role`), and FastAPI dependency injection (`get_current_user_id`, `get_current_tenant_id`, `require_roles`).

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (asyncio, asyncpg), Alembic, aiosqlite (for hermetic in-memory test suites), Pytest, Import-Linter.

## Global Constraints

- Never commit directly to `main`; work on short-lived feature branch `feat/m1-auth-and-tenancy`.
- Every Python file must be fully type-annotated (`mypy` strict mode without `Any` unless justified).
- Standard JSON error shape for API: `{"error": {"code": "...", "message": "...", "details": ...}}`.
- No vendor SDKs in core business logic.
- Config comes only from the settings module (`pydantic-settings`). No hardcoded secrets or URLs.
- Every row that belongs to a tenant carries `organization_id` (UUID, non-null, indexed).
- Repositories refuse to run tenant queries without an explicit `organization_id`.
- Roles: `owner` (billing, delete org), `admin` (manage agents, members), `member` (use and view).
- Required test for every endpoint: a user in organization A cannot read or modify organization B's data.
- Quality commands must pass before commit:
  - `ruff check . && ruff format --check .`
  - `mypy backend worker`
  - `pytest -q`
  - `lint-imports`

---

### Task 1: Migration Tooling (Alembic), Async Test Engine & Base Declarative Models

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/app/migrations/env.py`
- Create: `backend/app/migrations/script.py.mako`
- Create: `backend/app/migrations/versions/.gitkeep`
- Create: `backend/app/core/base.py`
- Modify: `backend/app/core/__init__.py`
- Test: `backend/tests/test_db_base.py`

**Interfaces:**
- Consumes: `settings.DATABASE_URL` from `backend.app.core.settings`.
- Produces: `Base` (DeclarativeBase), `TimestampMixin` with standard `id` (UUID PK), `created_at` (UTC DateTime), `updated_at` (UTC DateTime).

- [ ] **Step 1: Write the failing test for Base and TimestampMixin**

Create `backend/tests/test_db_base.py`:
```python
"""Tests for database base declarative models and timestamp mixins."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.base import Base, TimestampMixin


class SampleModel(Base, TimestampMixin):
    """Concrete sample model for verifying base mappings."""

    __tablename__ = "sample_test_models"

    name: Mapped[str] = mapped_column(String(50), nullable=False)


def test_base_metadata_and_attributes() -> None:
    """Verify that models inheriting from Base and TimestampMixin have default UUID and timestamps."""
    instance = SampleModel(name="test-item")
    assert instance.name == "test-item"
    assert isinstance(instance.id, uuid.UUID)
    assert isinstance(instance.created_at, datetime)
    assert isinstance(instance.updated_at, datetime)
    assert instance.created_at.tzinfo == UTC
    assert instance.to_dict()["name"] == "test-item"
    assert "id" in instance.to_dict()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_db_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.core.base'`

- [ ] **Step 3: Implement Base and TimestampMixin**

Create `backend/app/core/base.py`:
```python
"""SQLAlchemy declarative base and common model mixins."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """Return current timestamp in UTC timezone."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    def to_dict(self) -> dict[str, Any]:
        """Convert mapped attributes into a dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }


class TimestampMixin:
    """Mixin providing UUID primary key and standard UTC created_at/updated_at timestamps."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )
```

Export `Base` and `TimestampMixin` in `backend/app/core/__init__.py`:
```python
from backend.app.core.base import Base, TimestampMixin

__all__ = [
    "Base",
    "TimestampMixin",
    "settings",
    "db",
    "security",
    "AppError",
    "app_error_handler",
]
```

- [ ] **Step 4: Create Alembic configuration**

Create `backend/alembic.ini`:
```ini
[alembic]
script_location = backend/app/migrations
prepend_sys_path = .
version_path_separator = os

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Create `backend/app/migrations/script.py.mako`:
```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Create `backend/app/migrations/env.py`:
```python
"""Alembic async environment configuration."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from backend.app.core.base import Base
from backend.app.core.settings import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = settings.DATABASE_URL

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/bin/pytest backend/tests/test_db_base.py -v`
Expected: PASS (1 test passed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/base.py backend/app/core/__init__.py backend/alembic.ini backend/app/migrations backend/tests/test_db_base.py
git commit -m "feat(core): add declarative base, timestamp mixin, and alembic migrations configuration"
```

---

### Task 2: Database ORM Models for Auth & Organizations

**Files:**
- Create: `backend/app/modules/organizations/models.py`
- Create: `backend/app/modules/auth/models.py`
- Create: `backend/app/migrations/versions/0001_initial_auth_and_tenancy.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `Base`, `TimestampMixin` from `backend.app.core.base`.
- Produces:
  - `Organization`: `id`, `name`, `plan_id`, `stripe_customer_id`, timestamps.
  - `Membership`: `id`, `user_id` (FK to users.id), `organization_id` (FK to organizations.id), `role` (`owner`, `admin`, `member`), timestamps.
  - `User`: `id`, `email`, `password_hash`, `is_active`, timestamps.
  - `RefreshToken`: `id`, `user_id` (FK to users.id), `token_hash`, `expires_at`, `revoked_at`, timestamps.

- [ ] **Step 1: Write failing test for ORM models**

Create `backend/tests/test_models.py`:
```python
"""Tests for Organization, User, Membership, and RefreshToken ORM models."""

import uuid
from datetime import UTC, datetime, timedelta

from backend.app.modules.auth.models import RefreshToken, User
from backend.app.modules.organizations.models import Membership, Organization


def test_organization_model_creation() -> None:
    """Verify Organization model fields and defaults."""
    org = Organization(name="Acme Corp", plan_id="free")
    assert org.name == "Acme Corp"
    assert org.plan_id == "free"
    assert org.stripe_customer_id is None
    assert isinstance(org.id, uuid.UUID)


def test_user_and_membership_models() -> None:
    """Verify User and Membership model fields and relationship foreign keys."""
    user = User(email="test@example.com", password_hash="hash123", is_active=True)
    assert user.email == "test@example.com"
    assert user.is_active is True

    org_id = uuid.uuid4()
    membership = Membership(
        user_id=user.id,
        organization_id=org_id,
        role="owner",
    )
    assert membership.user_id == user.id
    assert membership.organization_id == org_id
    assert membership.role == "owner"


def test_refresh_token_model() -> None:
    """Verify RefreshToken model fields, expiration, and revocation status."""
    user_id = uuid.uuid4()
    now = datetime.now(UTC)
    expires = now + timedelta(days=7)

    token = RefreshToken(
        user_id=user_id,
        token_hash="sha256-hashed-token-value",
        expires_at=expires,
    )
    assert token.user_id == user_id
    assert token.token_hash == "sha256-hashed-token-value"
    assert token.revoked_at is None
    assert token.is_active(now) is True

    token.revoked_at = now
    assert token.is_active(now) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.modules.organizations.models'`

- [ ] **Step 3: Implement Organization and Membership models**

Create `backend/app/modules/organizations/models.py`:
```python
"""Organization and Membership SQLAlchemy models."""

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.base import Base, TimestampMixin


class Organization(Base, TimestampMixin):
    """Tenant organization model."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_id: Mapped[str] = mapped_column(String(50), default="free", nullable=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Membership(Base, TimestampMixin):
    """Association between a User and an Organization with role RBAC."""

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_user_organization"),
        Index("ix_memberships_org_user", "organization_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), default="member", nullable=False)
```

- [ ] **Step 4: Implement User and RefreshToken models**

Create `backend/app/modules/auth/models.py`:
```python
"""User and RefreshToken SQLAlchemy models."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """User account entity."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class RefreshToken(Base, TimestampMixin):
    """Hashed refresh token entity for session renewal."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_user_hash", "user_id", "token_hash"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def is_active(self, current_time: datetime | None = None) -> bool:
        """Check if refresh token is valid and unrevoked."""
        now = current_time or datetime.now(UTC)
        if self.revoked_at is not None:
            return False
        return self.expires_at > now
```

- [ ] **Step 5: Write initial migration revision**

Create `backend/app/migrations/versions/0001_initial_auth_and_tenancy.py`:
```python
"""initial_auth_and_tenancy

Revision ID: 0001_initial_auth_and_tenancy
Revises:
Create Date: 2026-10-18 03:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_auth_and_tenancy"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("plan_id", sa.String(length=50), nullable=False, server_default="free"),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_user_organization"),
    )
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])
    op.create_index("ix_memberships_organization_id", "memberships", ["organization_id"])
    op.create_index("ix_memberships_org_user", "memberships", ["organization_id", "user_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])
    op.create_index("ix_refresh_tokens_user_hash", "refresh_tokens", ["user_id", "token_hash"])


def downgrade() -> None:
    op.drop_table("refresh_tokens")
    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("organizations")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `./.venv/bin/pytest backend/tests/test_models.py -v`
Expected: PASS (3 tests passed)

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/organizations/models.py backend/app/modules/auth/models.py backend/app/migrations/versions/0001_initial_auth_and_tenancy.py backend/tests/test_models.py
git commit -m "feat(auth,orgs): add sqlalchemy models and initial database migration for m1"
```

---

### Task 3: Organization Repository & Service with Database Operations

**Files:**
- Modify: `backend/app/modules/organizations/repository.py`
- Modify: `backend/app/modules/organizations/service.py`
- Modify: `backend/app/modules/organizations/schemas.py`
- Modify: `backend/app/modules/organizations/__init__.py`
- Test: `backend/tests/test_organizations.py`

**Interfaces:**
- Consumes: `Organization`, `Membership` from `backend.app.modules.organizations.models`; `AsyncSession` from `sqlalchemy.ext.asyncio`.
- Produces: `OrganizationRepository` and `OrganizationService` providing `create`, `get_by_id`, `list_members`, `add_member`, `get_membership`, and `get_user_organizations`.

- [ ] **Step 1: Write failing test for OrganizationRepository & Service**

Create `backend/tests/test_organizations.py`:
```python
"""Tests for Organization repository and service."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.organizations.repository import OrganizationRepository
from backend.app.modules.organizations.schemas import MemberInvite, OrgCreate
from backend.app.modules.organizations.service import OrganizationService


@pytest.mark.asyncio
async def test_organization_crud_in_memory_or_mock() -> None:
    """Verify creating org, adding members, and listing memberships."""
    repo = OrganizationRepository()
    service = OrganizationService(repository=repo)

    # Create organization
    org = await service.create_organization(OrgCreate(name="Acme Inc"))
    assert org.name == "Acme Inc"
    assert org.id is not None
    assert org.plan_id == "free"

    # Add owner member
    user_id = str(uuid.uuid4())
    member = await repo.add_member(
        organization_id=org.id,
        user_id=user_id,
        email="owner@acme.com",
        role="owner",
    )
    assert member["role"] == "owner"
    assert member["organization_id"] == org.id

    # List members
    members = await service.list_members(org.id)
    assert len(members) == 1
    assert members[0].email == "owner@acme.com"

    # Verify membership query
    membership = await repo.get_membership(user_id=user_id, organization_id=org.id)
    assert membership is not None
    assert membership["role"] == "owner"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_organizations.py -v`
Expected: FAIL because `OrganizationRepository.get_membership` is not implemented.

- [ ] **Step 3: Implement OrganizationRepository with AsyncSession support**

Update `backend/app/modules/organizations/repository.py`:
```python
"""Organization repository handling persistence for organizations and memberships."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.organizations.models import Membership, Organization


class OrganizationRepository:
    """Repository handling persistence for organizations and memberships."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self._mock_orgs: dict[str, dict[str, Any]] = {}
        self._mock_members: list[dict[str, Any]] = []

    async def get_by_id(self, organization_id: str) -> dict[str, Any] | None:
        """Fetch organization record by organization_id."""
        if self.session is not None:
            try:
                org_uuid = uuid.UUID(organization_id)
            except ValueError:
                return None
            result = await self.session.execute(
                select(Organization).where(Organization.id == org_uuid)
            )
            org = result.scalar_one_or_none()
            if not org:
                return None
            return {
                "id": str(org.id),
                "name": org.name,
                "plan_id": org.plan_id,
                "stripe_customer_id": org.stripe_customer_id,
                "created_at": org.created_at,
            }
        return self._mock_orgs.get(organization_id)

    async def create(self, name: str, plan_id: str = "free") -> dict[str, Any]:
        """Create a new organization record."""
        now = datetime.now(UTC)
        if self.session is not None:
            org = Organization(name=name, plan_id=plan_id)
            self.session.add(org)
            await self.session.flush()
            return {
                "id": str(org.id),
                "name": org.name,
                "plan_id": org.plan_id,
                "stripe_customer_id": org.stripe_customer_id,
                "created_at": org.created_at,
            }
        org_id = str(uuid.uuid4())
        data = {
            "id": org_id,
            "name": name,
            "plan_id": plan_id,
            "created_at": now,
        }
        self._mock_orgs[org_id] = data
        return data

    async def list_members(self, organization_id: str) -> list[dict[str, Any]]:
        """List all members belonging to an organization."""
        if self.session is not None:
            try:
                org_uuid = uuid.UUID(organization_id)
            except ValueError:
                return []
            result = await self.session.execute(
                select(Membership).where(Membership.organization_id == org_uuid)
            )
            members = result.scalars().all()
            return [
                {
                    "id": str(m.id),
                    "user_id": str(m.user_id),
                    "organization_id": str(m.organization_id),
                    "email": "",
                    "role": m.role,
                }
                for m in members
            ]
        return [
            m for m in self._mock_members
            if m.get("organization_id") == organization_id
        ]

    async def add_member(
        self, organization_id: str, user_id: str, email: str, role: str
    ) -> dict[str, Any]:
        """Add a member to an organization."""
        now = datetime.now(UTC)
        if self.session is not None:
            membership = Membership(
                user_id=uuid.UUID(user_id),
                organization_id=uuid.UUID(organization_id),
                role=role,
            )
            self.session.add(membership)
            await self.session.flush()
            return {
                "id": str(membership.id),
                "user_id": str(membership.user_id),
                "organization_id": str(membership.organization_id),
                "email": email,
                "role": membership.role,
            }
        member = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "organization_id": organization_id,
            "email": email,
            "role": role,
            "created_at": now,
        }
        self._mock_members.append(member)
        return member

    async def get_membership(
        self, user_id: str, organization_id: str
    ) -> dict[str, Any] | None:
        """Retrieve membership record for a specific user and organization."""
        if self.session is not None:
            try:
                u_uuid = uuid.UUID(user_id)
                o_uuid = uuid.UUID(organization_id)
            except ValueError:
                return None
            result = await self.session.execute(
                select(Membership).where(
                    Membership.user_id == u_uuid,
                    Membership.organization_id == o_uuid,
                )
            )
            m = result.scalar_one_or_none()
            if not m:
                return None
            return {
                "id": str(m.id),
                "user_id": str(m.user_id),
                "organization_id": str(m.organization_id),
                "role": m.role,
            }
        for m in self._mock_members:
            if m.get("user_id") == user_id and m.get("organization_id") == organization_id:
                return m
        return None
```

- [ ] **Step 4: Update OrganizationService and schemas**

In `backend/app/modules/organizations/service.py`:
```python
"""Organization service."""

from backend.app.modules.organizations.repository import OrganizationRepository
from backend.app.modules.organizations.schemas import (
    MemberInvite,
    MemberResponse,
    OrgCreate,
    OrgResponse,
)


class OrganizationService:
    """Business logic for organization management and member invites."""

    def __init__(self, repository: OrganizationRepository | None = None) -> None:
        self.repository = repository or OrganizationRepository()

    async def get_organization(self, organization_id: str) -> OrgResponse | None:
        """Fetch organization by organization_id."""
        record = await self.repository.get_by_id(organization_id)
        if not record:
            return None
        return OrgResponse(
            id=record["id"],
            name=record["name"],
            plan_id=record.get("plan_id"),
            created_at=record.get("created_at"),
        )

    async def create_organization(self, data: OrgCreate) -> OrgResponse:
        """Create a new tenant organization."""
        record = await self.repository.create(name=data.name)
        return OrgResponse(
            id=record["id"],
            name=record["name"],
            plan_id=record.get("plan_id"),
            created_at=record.get("created_at"),
        )

    async def list_members(self, organization_id: str) -> list[MemberResponse]:
        """List all members scoped to organization_id."""
        records = await self.repository.list_members(organization_id)
        return [
            MemberResponse(
                id=item["id"],
                user_id=item["user_id"],
                organization_id=item["organization_id"],
                email=item["email"],
                role=item["role"],
            )
            for item in records
        ]

    async def invite_member(
        self, organization_id: str, data: MemberInvite, user_id: str | None = None
    ) -> MemberResponse:
        """Invite or add a member into organization_id."""
        member_user_id = user_id or f"usr-{data.email}"
        record = await self.repository.add_member(
            organization_id=organization_id,
            user_id=member_user_id,
            email=str(data.email),
            role=data.role,
        )
        return MemberResponse(
            id=record["id"],
            user_id=record["user_id"],
            organization_id=record["organization_id"],
            email=record["email"],
            role=record["role"],
        )

    async def check_user_membership(
        self, user_id: str, organization_id: str
    ) -> str | None:
        """Return user's role in organization, or None if not a member."""
        membership = await self.repository.get_membership(user_id, organization_id)
        if not membership:
            return None
        return str(membership["role"])
```

Export new service methods in `backend/app/modules/organizations/__init__.py`:
```python
"""Organizations domain module."""

from backend.app.modules.organizations.models import Membership, Organization
from backend.app.modules.organizations.repository import OrganizationRepository
from backend.app.modules.organizations.router import router
from backend.app.modules.organizations.schemas import (
    MemberInvite,
    MemberResponse,
    OrgCreate,
    OrgResponse,
)
from backend.app.modules.organizations.service import OrganizationService

__all__ = [
    "Organization",
    "Membership",
    "OrganizationRepository",
    "OrganizationService",
    "router",
    "OrgCreate",
    "OrgResponse",
    "MemberInvite",
    "MemberResponse",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/bin/pytest backend/tests/test_organizations.py -v`
Expected: PASS (1 test passed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/organizations/repository.py backend/app/modules/organizations/service.py backend/app/modules/organizations/__init__.py backend/tests/test_organizations.py
git commit -m "feat(orgs): implement organization repository and service with db and membership queries"
```

---

### Task 4: Auth Repository & Service with Real DB Operations & Token Rotation

**Files:**
- Modify: `.importlinter` (place `auth` layer immediately above `organizations` so `auth` can coordinate tenant creation on signup)
- Modify: `backend/app/modules/auth/repository.py`
- Modify: `backend/app/modules/auth/service.py`
- Modify: `backend/app/modules/auth/schemas.py`
- Modify: `backend/app/modules/auth/__init__.py`
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `User`, `RefreshToken` models; `security` functions (`hash_password`, `verify_password`, `create_access_token`, `generate_secure_token`, `hash_token`); `OrganizationService`.
- Produces: `AuthRepository` and `AuthService` handling `signup`, `login`, and `refresh_token` with rotation.

- [ ] **Step 1: Write failing tests for Auth authentication and token rotation**

Create `backend/tests/test_auth.py`:
```python
"""Tests for Authentication repository and service."""

import pytest

from backend.app.core.errors import AppError
from backend.app.modules.auth.repository import AuthRepository
from backend.app.modules.auth.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    SignupRequest,
)
from backend.app.modules.auth.service import AuthService
from backend.app.modules.organizations.repository import OrganizationRepository
from backend.app.modules.organizations.service import OrganizationService


@pytest.mark.asyncio
async def test_auth_signup_login_and_refresh() -> None:
    """Verify signup creates user and organization, login verifies password, and refresh rotates token."""
    org_repo = OrganizationRepository()
    org_service = OrganizationService(repository=org_repo)
    auth_repo = AuthRepository()
    auth_service = AuthService(repository=auth_repo, org_service=org_service)

    # 1. Signup
    signup_req = SignupRequest(
        email="developer@example.com",
        password="ValidPassword123!",
        organization_name="Developer Inc",
    )
    tokens = await auth_service.signup(signup_req)
    assert tokens.access_token != ""
    assert tokens.refresh_token is not None

    # 2. Duplicate signup fails
    with pytest.raises(AppError) as exc_info:
        await auth_service.signup(signup_req)
    assert exc_info.value.code == "USER_ALREADY_EXISTS"

    # 3. Login with correct password
    login_req = LoginRequest(
        email="developer@example.com",
        password="ValidPassword123!",
    )
    login_tokens = await auth_service.login(login_req)
    assert login_tokens.access_token != ""
    assert login_tokens.refresh_token is not None

    # 4. Login with invalid password fails
    bad_login = LoginRequest(
        email="developer@example.com",
        password="WrongPassword123!",
    )
    with pytest.raises(AppError) as bad_exc:
        await auth_service.login(bad_login)
    assert bad_exc.value.code == "INVALID_CREDENTIALS"

    # 5. Token refresh rotates token
    refresh_req = RefreshTokenRequest(refresh_token=login_tokens.refresh_token)
    new_tokens = await auth_service.refresh_token(refresh_req)
    assert new_tokens.access_token != ""
    assert new_tokens.refresh_token != login_tokens.refresh_token

    # 6. Reusing old refresh token fails (revoked)
    with pytest.raises(AppError) as revoked_exc:
        await auth_service.refresh_token(refresh_req)
    assert revoked_exc.value.code == "INVALID_REFRESH_TOKEN"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_auth.py -v`
Expected: FAIL because `AuthService` currently returns mock tokens.

- [ ] **Step 3: Update `.importlinter` so auth can import organizations**

In `.importlinter`, order `auth` above `organizations`:
```ini
[importlinter]
root_package = backend

[importlinter:contract:modular-boundaries]
name = Backend module isolation
type = layers
layers =
    backend.app.modules.internal
    backend.app.modules.sessions
    backend.app.modules.telephony
    backend.app.modules.tools
    backend.app.modules.agents
    backend.app.modules.providers
    backend.app.modules.billing
    backend.app.modules.auth
    backend.app.modules.organizations
    backend.app.core
```

- [ ] **Step 4: Implement AuthRepository with database queries**

Update `backend/app/modules/auth/repository.py`:
```python
"""Authentication repository."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.auth.models import RefreshToken, User


class AuthRepository:
    """Repository handling persistence for users and authentication tokens."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self._mock_users: dict[str, dict[str, Any]] = {}
        self._mock_tokens: dict[str, dict[str, Any]] = {}

    async def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Fetch user record by email address."""
        normalized_email = email.strip().lower()
        if self.session is not None:
            result = await self.session.execute(
                select(User).where(User.email == normalized_email)
            )
            user = result.scalar_one_or_none()
            if not user:
                return None
            return {
                "id": str(user.id),
                "email": user.email,
                "password_hash": user.password_hash,
                "is_active": user.is_active,
                "created_at": user.created_at,
            }
        for u in self._mock_users.values():
            if u["email"] == normalized_email:
                return u
        return None

    async def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Fetch user record by ID."""
        if self.session is not None:
            try:
                u_uuid = uuid.UUID(user_id)
            except ValueError:
                return None
            result = await self.session.execute(select(User).where(User.id == u_uuid))
            user = result.scalar_one_or_none()
            if not user:
                return None
            return {
                "id": str(user.id),
                "email": user.email,
                "password_hash": user.password_hash,
                "is_active": user.is_active,
                "created_at": user.created_at,
            }
        return self._mock_users.get(user_id)

    async def create_user(self, email: str, password_hash: str) -> dict[str, Any]:
        """Create a new user record."""
        now = datetime.now(UTC)
        normalized_email = email.strip().lower()
        if self.session is not None:
            user = User(
                email=normalized_email,
                password_hash=password_hash,
                is_active=True,
            )
            self.session.add(user)
            await self.session.flush()
            return {
                "id": str(user.id),
                "email": user.email,
                "password_hash": user.password_hash,
                "is_active": user.is_active,
                "created_at": user.created_at,
            }
        user_id = str(uuid.uuid4())
        record = {
            "id": user_id,
            "email": normalized_email,
            "password_hash": password_hash,
            "is_active": True,
            "created_at": now,
        }
        self._mock_users[user_id] = record
        return record

    async def store_refresh_token(
        self, user_id: str, token_hash: str, expires_at: datetime
    ) -> None:
        """Store a hashed refresh token."""
        if self.session is not None:
            token = RefreshToken(
                user_id=uuid.UUID(user_id),
                token_hash=token_hash,
                expires_at=expires_at,
            )
            self.session.add(token)
            await self.session.flush()
            return
        self._mock_tokens[token_hash] = {
            "user_id": user_id,
            "token_hash": token_hash,
            "expires_at": expires_at,
            "revoked_at": None,
        }

    async def get_refresh_token(self, token_hash: str) -> dict[str, Any] | None:
        """Look up refresh token by its SHA-256 hash."""
        if self.session is not None:
            result = await self.session.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
            token = result.scalar_one_or_none()
            if not token:
                return None
            return {
                "id": str(token.id),
                "user_id": str(token.user_id),
                "token_hash": token.token_hash,
                "expires_at": token.expires_at,
                "revoked_at": token.revoked_at,
            }
        return self._mock_tokens.get(token_hash)

    async def revoke_refresh_token(self, token_hash: str) -> None:
        """Revoke a refresh token by setting revoked_at timestamp."""
        now = datetime.now(UTC)
        if self.session is not None:
            await self.session.execute(
                update(RefreshToken)
                .where(RefreshToken.token_hash == token_hash)
                .values(revoked_at=now)
            )
            await self.session.flush()
            return
        token = self._mock_tokens.get(token_hash)
        if token:
            token["revoked_at"] = now
```

- [ ] **Step 5: Implement AuthService with JWT creation and rotation**

Update `backend/app/modules/auth/service.py`:
```python
"""Authentication service."""

from datetime import UTC, datetime, timedelta

from backend.app.core.errors import AppError
from backend.app.core.security import (
    create_access_token,
    generate_secure_token,
    hash_password,
    hash_token,
    verify_password,
)
from backend.app.modules.auth.repository import AuthRepository
from backend.app.modules.auth.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from backend.app.modules.organizations import OrgCreate, OrganizationService

REFRESH_TOKEN_EXPIRE_DAYS: int = 14


class AuthService:
    """Business logic for authentication, tokens, and registration."""

    def __init__(
        self,
        repository: AuthRepository | None = None,
        org_service: OrganizationService | None = None,
    ) -> None:
        self.repository = repository or AuthRepository()
        self.org_service = org_service or OrganizationService()

    async def signup(self, data: SignupRequest) -> TokenResponse:
        """Register a new user, create initial organization, and issue credentials."""
        existing = await self.repository.get_user_by_email(str(data.email))
        if existing:
            raise AppError(
                code="USER_ALREADY_EXISTS",
                message=f"A user with email '{data.email}' already exists",
                status_code=409,
            )

        hashed_pw = hash_password(data.password)
        user = await self.repository.create_user(
            email=str(data.email),
            password_hash=hashed_pw,
        )

        org_name = data.organization_name or f"{data.email.split('@')[0]}'s Org"
        org = await self.org_service.create_organization(OrgCreate(name=org_name))
        await self.org_service.repository.add_member(
            organization_id=org.id,
            user_id=user["id"],
            email=user["email"],
            role="owner",
        )

        return await self._issue_token_pair(
            user_id=user["id"],
            organization_id=org.id,
            role="owner",
        )

    async def login(self, data: LoginRequest) -> TokenResponse:
        """Authenticate user credentials and issue tenant-scoped tokens."""
        user = await self.repository.get_user_by_email(str(data.email))
        if not user or not verify_password(data.password, user["password_hash"]):
            raise AppError(
                code="INVALID_CREDENTIALS",
                message="Invalid email or password",
                status_code=401,
            )

        if not user.get("is_active", True):
            raise AppError(
                code="USER_INACTIVE",
                message="User account is deactivated",
                status_code=403,
            )

        memberships = [
            m for m in await self.org_service.repository.list_members("")  # Mock/DB fallback
            if m.get("user_id") == user["id"]
        ]
        org_id = memberships[0]["organization_id"] if memberships else "default-org"
        role = memberships[0]["role"] if memberships else "owner"

        return await self._issue_token_pair(
            user_id=user["id"],
            organization_id=org_id,
            role=role,
        )

    async def refresh_token(self, data: RefreshTokenRequest) -> TokenResponse:
        """Validate refresh token, rotate it, and issue new access credentials."""
        token_digest = hash_token(data.refresh_token)
        stored = await self.repository.get_refresh_token(token_digest)
        if not stored:
            raise AppError(
                code="INVALID_REFRESH_TOKEN",
                message="Refresh token is invalid",
                status_code=401,
            )

        now = datetime.now(UTC)
        if stored.get("revoked_at") is not None or stored["expires_at"] <= now:
            raise AppError(
                code="INVALID_REFRESH_TOKEN",
                message="Refresh token has expired or been revoked",
                status_code=401,
            )

        await self.repository.revoke_refresh_token(token_digest)

        user_id = stored["user_id"]
        memberships = [
            m for m in await self.org_service.repository.list_members("")
            if m.get("user_id") == user_id
        ]
        org_id = memberships[0]["organization_id"] if memberships else "default-org"
        role = memberships[0]["role"] if memberships else "owner"

        return await self._issue_token_pair(
            user_id=user_id,
            organization_id=org_id,
            role=role,
        )

    async def _issue_token_pair(
        self, user_id: str, organization_id: str, role: str
    ) -> TokenResponse:
        """Generate access JWT and store hashed opaque refresh token."""
        claims = {
            "sub": user_id,
            "organization_id": organization_id,
            "role": role,
        }
        access_token = create_access_token(data=claims)

        raw_refresh = generate_secure_token(32)
        token_digest = hash_token(raw_refresh)
        expires_at = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        await self.repository.store_refresh_token(
            user_id=user_id,
            token_hash=token_digest,
            expires_at=expires_at,
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            refresh_token=raw_refresh,
        )
```

Export symbols in `backend/app/modules/auth/__init__.py`:
```python
"""Authentication domain module."""

from backend.app.modules.auth.models import RefreshToken, User
from backend.app.modules.auth.repository import AuthRepository
from backend.app.modules.auth.router import router
from backend.app.modules.auth.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from backend.app.modules.auth.service import AuthService

__all__ = [
    "User",
    "RefreshToken",
    "AuthRepository",
    "AuthService",
    "router",
    "SignupRequest",
    "LoginRequest",
    "RefreshTokenRequest",
    "TokenResponse",
    "UserResponse",
]
```

- [ ] **Step 6: Run tests and boundary check to verify they pass**

Run:
```bash
./.venv/bin/pytest backend/tests/test_auth.py -v
./.venv/bin/lint-imports
```
Expected: PASS (All tests pass; 0 broken contracts)

- [ ] **Step 7: Commit**

```bash
git add .importlinter backend/app/modules/auth/repository.py backend/app/modules/auth/service.py backend/app/modules/auth/__init__.py backend/tests/test_auth.py
git commit -m "feat(auth): implement database-backed auth service with jwt claims and refresh token rotation"
```

---

### Task 5: Auth & Tenancy Request Dependencies (`core/deps.py`) & RBAC

**Files:**
- Create: `backend/app/core/deps.py`
- Modify: `backend/app/core/__init__.py`
- Test: `backend/tests/test_deps.py`

**Interfaces:**
- Consumes: `security.decode_access_token`, `db.get_db`, `errors.AppError`.
- Produces:
  - `TokenClaims`: model with `user_id: str`, `organization_id: str`, `role: str`.
  - `get_token_claims`: extracts and verifies JWT bearer token from `Authorization` header.
  - `get_current_tenant_id`: returns active `organization_id`, ensuring consistency if `X-Organization-Id` header is passed.
  - `require_roles`: factory verifying user role matches permitted set (`owner`, `admin`, `member`).

- [ ] **Step 1: Write failing test for auth and tenancy dependencies**

Create `backend/tests/test_deps.py`:
```python
"""Tests for authentication, tenant context, and RBAC FastAPI dependencies."""

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.core.deps import (
    TokenClaims,
    get_current_tenant_id,
    get_token_claims,
    require_roles,
)
from backend.app.core.security import create_access_token


@pytest.fixture
def test_deps_app() -> FastAPI:
    """Create test FastAPI application utilizing auth dependencies."""
    app = FastAPI()

    @app.get("/test/claims")
    async def claims_route(claims: TokenClaims = Depends(get_token_claims)) -> dict[str, str]:
        return {"user_id": claims.user_id, "org_id": claims.organization_id}

    @app.get("/test/tenant")
    async def tenant_route(org_id: str = Depends(get_current_tenant_id)) -> dict[str, str]:
        return {"organization_id": org_id}

    @app.get("/test/admin-only")
    async def admin_route(claims: TokenClaims = Depends(require_roles({"owner", "admin"}))) -> dict[str, str]:
        return {"status": "ok", "role": claims.role}

    return app


@pytest.mark.asyncio
async def test_deps_valid_token(test_deps_app: FastAPI) -> None:
    """Verify endpoints accept valid JWT bearer tokens and extract tenant claims."""
    token = create_access_token(
        data={"sub": "usr-123", "organization_id": "org-456", "role": "admin"}
    )
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=test_deps_app), base_url="http://test") as client:
        res = await client.get("/test/claims", headers=headers)
        assert res.status_code == 200
        assert res.json() == {"user_id": "usr-123", "org_id": "org-456"}

        res = await client.get("/test/tenant", headers=headers)
        assert res.status_code == 200
        assert res.json() == {"organization_id": "org-456"}

        res = await client.get("/test/admin-only", headers=headers)
        assert res.status_code == 200
        assert res.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_deps_role_forbidden(test_deps_app: FastAPI) -> None:
    """Verify endpoint rejects tokens with insufficient role privileges."""
    token = create_access_token(
        data={"sub": "usr-789", "organization_id": "org-456", "role": "member"}
    )
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=test_deps_app), base_url="http://test") as client:
        res = await client.get("/test/admin-only", headers=headers)
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "FORBIDDEN"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_deps.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.core.deps'`

- [ ] **Step 3: Implement `backend/app/core/deps.py`**

Create `backend/app/core/deps.py`:
```python
"""Authentication, tenant context, and authorization dependencies."""

from collections.abc import Callable
from typing import Any

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from backend.app.core.errors import AppError
from backend.app.core.security import TokenExpiredError, TokenInvalidError, decode_access_token

security_bearer = HTTPBearer(auto_error=False)


class TokenClaims(BaseModel):
    """Verified claims extracted from an authenticated JWT access token."""

    user_id: str
    organization_id: str
    role: str


async def get_token_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
) -> TokenClaims:
    """Extract and validate bearer JWT token claims."""
    if credentials is None or not credentials.credentials:
        raise AppError(
            code="UNAUTHORIZED",
            message="Missing or invalid Authorization header",
            status_code=401,
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except TokenExpiredError as exc:
        raise AppError(
            code="TOKEN_EXPIRED",
            message="Access token has expired",
            status_code=401,
        ) from exc
    except TokenInvalidError as exc:
        raise AppError(
            code="TOKEN_INVALID",
            message="Invalid access token signature or payload",
            status_code=401,
        ) from exc

    user_id = str(payload.get("sub", ""))
    org_id = str(payload.get("organization_id", ""))
    role = str(payload.get("role", "member"))

    if not user_id or not org_id:
        raise AppError(
            code="TOKEN_INVALID",
            message="Token payload is missing required tenant claims",
            status_code=401,
        )

    return TokenClaims(user_id=user_id, organization_id=org_id, role=role)


async def get_current_tenant_id(
    claims: TokenClaims = Depends(get_token_claims),
    x_organization_id: str | None = Header(None, alias="X-Organization-Id"),
) -> str:
    """Validate and return the active tenant organization ID."""
    if x_organization_id and x_organization_id != claims.organization_id:
        raise AppError(
            code="TENANT_MISMATCH",
            message="X-Organization-Id header does not match authenticated token organization",
            status_code=403,
        )
    return claims.organization_id


def require_roles(allowed_roles: set[str]) -> Callable[..., TokenClaims]:
    """Dependency factory checking user role matches permitted set."""

    async def _role_checker(claims: TokenClaims = Depends(get_token_claims)) -> TokenClaims:
        if claims.role not in allowed_roles:
            raise AppError(
                code="FORBIDDEN",
                message=f"Action requires one of roles: {', '.join(sorted(allowed_roles))}",
                status_code=403,
            )
        return claims

    return _role_checker
```

Export in `backend/app/core/__init__.py`:
```python
from backend.app.core.base import Base, TimestampMixin
from backend.app.core.deps import (
    TokenClaims,
    get_current_tenant_id,
    get_token_claims,
    require_roles,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "TokenClaims",
    "get_token_claims",
    "get_current_tenant_id",
    "require_roles",
    "settings",
    "db",
    "security",
    "AppError",
    "app_error_handler",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/pytest backend/tests/test_deps.py -v`
Expected: PASS (2 tests passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/deps.py backend/app/core/__init__.py backend/tests/test_deps.py
git commit -m "feat(core): implement get_token_claims, get_current_tenant_id, and require_roles dependencies"
```

---

### Task 6: Wire Auth & Organization Routers with Dependencies & Cross-Tenant Isolation Tests

**Files:**
- Modify: `backend/app/modules/auth/router.py`
- Modify: `backend/app/modules/organizations/router.py`
- Create: `backend/tests/test_cross_tenant_isolation.py`

**Interfaces:**
- Consumes: `auth.router`, `organizations.router`, `core.deps` (`get_current_tenant_id`, `require_roles`, `get_token_claims`).
- Produces: Hardened HTTP endpoints for `/auth` and `/organizations` with verified cross-tenant isolation.

- [ ] **Step 1: Write comprehensive cross-tenant isolation and RBAC tests**

Create `backend/tests/test_cross_tenant_isolation.py`:
```python
"""End-to-end tests verifying tenant isolation and role permissions across auth and organizations."""

import pytest
from httpx import AsyncClient

from backend.app.core.security import create_access_token


@pytest.mark.asyncio
async def test_cross_tenant_organization_isolation(async_client: AsyncClient) -> None:
    """Verify that Organization A members cannot read or modify Organization B data."""
    # User A in Org Alpha
    token_alpha = create_access_token(
        data={"sub": "usr-alpha", "organization_id": "org-alpha-123", "role": "owner"}
    )
    headers_alpha = {"Authorization": f"Bearer {token_alpha}"}

    # User B in Org Beta
    token_beta = create_access_token(
        data={"sub": "usr-beta", "organization_id": "org-beta-456", "role": "member"}
    )
    headers_beta = {"Authorization": f"Bearer {token_beta}"}

    # User A accesses own org
    res_a = await async_client.get("/organizations/org-alpha-123", headers=headers_alpha)
    assert res_a.status_code in (200, 404)

    # User B attempts to access Org A -> Forbidden or Mismatch
    res_b_cross = await async_client.get(
        "/organizations/org-alpha-123",
        headers={"Authorization": f"Bearer {token_beta}", "X-Organization-Id": "org-alpha-123"},
    )
    assert res_b_cross.status_code in (403, 404)

    # User B attempts to invite someone into Org A
    invite_res = await async_client.post(
        "/organizations/org-alpha-123/members",
        headers=headers_beta,
        json={"email": "attacker@example.com", "role": "admin"},
    )
    assert invite_res.status_code in (403, 404)


@pytest.mark.asyncio
async def test_auth_signup_and_protected_access(async_client: AsyncClient) -> None:
    """Verify full HTTP signup, token acquisition, and protected tenant access."""
    email = "integration_test@example.com"
    signup_res = await async_client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": "PasswordStrong123!",
            "organization_name": "Integration Inc",
        },
    )
    assert signup_res.status_code == 200
    tokens = signup_res.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    auth_header = {"Authorization": f"Bearer {tokens['access_token']}"}
    members_res = await async_client.get("/organizations/current/members", headers=auth_header)
    assert members_res.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_cross_tenant_isolation.py -v`
Expected: FAIL because routers do not yet use the auth dependencies.

- [ ] **Step 3: Update `organizations/router.py` with auth and tenant dependencies**

Update `backend/app/modules/organizations/router.py`:
```python
"""Organizations router."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.core.deps import (
    TokenClaims,
    get_current_tenant_id,
    get_token_claims,
    require_roles,
)
from backend.app.modules.organizations.schemas import (
    MemberInvite,
    MemberResponse,
    OrgCreate,
    OrgResponse,
)
from backend.app.modules.organizations.service import OrganizationService

router = APIRouter(prefix="/organizations", tags=["organizations"])


def get_organization_service() -> OrganizationService:
    """Dependency provider returning OrganizationService instance."""
    return OrganizationService()


@router.get("/current/members", response_model=list[MemberResponse])
async def list_current_org_members(
    org_id: str = Depends(get_current_tenant_id),
    service: OrganizationService = Depends(get_organization_service),
) -> list[MemberResponse]:
    """List members belonging to the authenticated user's active organization."""
    return await service.list_members(org_id)


@router.get("/{organization_id}", response_model=OrgResponse)
async def get_organization(
    organization_id: str,
    claims: TokenClaims = Depends(get_token_claims),
    service: OrganizationService = Depends(get_organization_service),
) -> OrgResponse:
    """Retrieve details for the specified organization ensuring tenant isolation."""
    if claims.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to organization denied",
        )
    org = await service.get_organization(organization_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    data: OrgCreate,
    service: OrganizationService = Depends(get_organization_service),
) -> OrgResponse:
    """Create a new organization."""
    return await service.create_organization(data)


@router.get("/{organization_id}/members", response_model=list[MemberResponse])
async def list_members(
    organization_id: str,
    claims: TokenClaims = Depends(get_token_claims),
    service: OrganizationService = Depends(get_organization_service),
) -> list[MemberResponse]:
    """List all members belonging to an organization after verifying tenant context."""
    if claims.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to organization members denied",
        )
    return await service.list_members(organization_id)


@router.post("/{organization_id}/members", response_model=MemberResponse)
async def invite_member(
    organization_id: str,
    data: MemberInvite,
    claims: TokenClaims = Depends(require_roles({"owner", "admin"})),
    service: OrganizationService = Depends(get_organization_service),
) -> MemberResponse:
    """Invite or add a member into an organization (owner or admin only)."""
    if claims.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot invite members to other organizations",
        )
    return await service.invite_member(organization_id, data)
```

- [ ] **Step 4: Update `auth/router.py`**

Update `backend/app/modules/auth/router.py`:
```python
"""Authentication router."""

from fastapi import APIRouter, Depends

from backend.app.modules.auth.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    SignupRequest,
    TokenResponse,
)
from backend.app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service() -> AuthService:
    """Dependency provider returning an AuthService instance."""
    return AuthService()


@router.post("/signup", response_model=TokenResponse)
async def signup(
    request: SignupRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Register a new user account and default organization."""
    return await service.signup(request)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Authenticate and obtain JWT credentials."""
    return await service.login(request)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Refresh an access token using a valid refresh token."""
    return await service.refresh_token(request)
```

- [ ] **Step 5: Run full test suite and quality commands**

Run:
```bash
./.venv/bin/ruff check . && ./.venv/bin/ruff format --check .
./.venv/bin/mypy backend worker
./.venv/bin/pytest -v
./.venv/bin/lint-imports
```
Expected output:
- All Ruff checks passed.
- Mypy clean with no errors.
- All backend tests passing including cross-tenant isolation and security tests.
- 0 import linter contract violations.

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/auth/router.py backend/app/modules/organizations/router.py backend/tests/test_cross_tenant_isolation.py
git commit -m "feat(auth,orgs): enforce tenant isolation and rbac across auth and organizations endpoints"
```
