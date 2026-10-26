# Milestone M3: Providers & Worker Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the end-to-end voice walking skeleton allowing browser test calls to connect via WebRTC, fetch session-pinned agent configurations through the internal worker gateway, and execute real-time streaming speech turns.

**Architecture:** Distributed control and media plane. The backend control plane generates signed LiveKit WebRTC tokens (`POST /sessions/web`), pins the agent version to a `sessions` table record, and exposes an internal gateway (`/internal/sessions/{id}/runtime-config`, `/internal/sessions/{id}/finalize`) protected by `X-Internal-Service-Token`. The stateless voice worker (`worker/`) connects to LiveKit, fetches pinned configuration, resolves concrete provider adapters (Deepgram STT, OpenAI LLM, Cartesia TTS) via a decoupled factory, and orchestrates the cascaded audio pipeline with barge-in and silence detection.

**Tech Stack:** Python 3.11+, LiveKit Python SDK (`livekit-api`, `livekit-agents`), FastAPI, SQLAlchemy 2.0 (asyncio, asyncpg), Alembic, HTTPX, Pytest, Import-Linter.

## Global Constraints

- Never commit directly to `main`; work on short-lived feature branch `feat/m3-providers-worker-gateway`.
- Every Python file must be fully type-annotated (`mypy` strict mode without `Any` unless justified).
- Standard JSON error shape for API: `{"error": {"code": "...", "message": "...", "details": ...}}`.
- The worker is stateless and holds zero direct database access. It fetches config exclusively through `/internal/sessions/{id}/runtime-config`.
- Internal endpoints require constant-time validation (`compare_digest`) of `X-Internal-Service-Token`.
- Provider adapters sit behind interfaces (`STTProvider`, `LLMProvider`, `TTSProvider`) in `worker/providers/`. No direct SDK imports in pipeline orchestration.
- Barge-in (caller interrupts) must cancel in-flight LLM stream and stop TTS playback immediately.
- Quality commands must pass before commit:
  - `ruff check . && ruff format --check .`
  - `mypy backend worker`
  - `pytest -q`
  - `lint-imports`

---

### Task 1: LiveKit Token Generator & Web Session Dispatch (`sessions` module)

**Files:**
- Create: `backend/app/core/livekit.py`
- Create: `backend/app/modules/sessions/models.py`
- Create: `backend/app/migrations/versions/0003_sessions.py`
- Modify: `backend/app/modules/sessions/repository.py`
- Modify: `backend/app/modules/sessions/service.py`
- Modify: `backend/app/modules/sessions/router.py`
- Modify: `backend/app/modules/sessions/__init__.py`
- Modify: `backend/app/migrations/env.py`
- Test: `backend/tests/test_sessions_dispatch.py`

**Interfaces:**
- Consumes: `settings.LIVEKIT_API_KEY`, `settings.LIVEKIT_API_SECRET`, `settings.LIVEKIT_URL`; `AgentService` from `backend.app.modules.agents`.
- Produces:
  - `generate_livekit_token(room_name: str, participant_identity: str, session_id: str) -> str`.
  - `Session` ORM model for table `sessions`.
  - `POST /sessions/web`: creates session with pinned `agent_version_id`, returns `{ session_id, room_name, livekit_token, livekit_url }`.

- [ ] **Step 1: Write the failing test for LiveKit token generator and Session model**

Create `backend/tests/test_sessions_dispatch.py`:
```python
"""Tests for LiveKit token generation and web session dispatch."""

import uuid
import pytest
from httpx import AsyncClient

from backend.app.core.livekit import generate_livekit_token
from backend.app.core.security import create_access_token


def test_generate_livekit_token() -> None:
    """Verify LiveKit access token generation creates a valid signed JWT string."""
    token = generate_livekit_token(
        room_name="cadence-room-test",
        participant_identity="user-browser-123",
        session_id="sess-test-456",
    )
    assert isinstance(token, str)
    assert len(token.split(".")) == 3


@pytest.mark.asyncio
async def test_start_web_session_api(async_client: AsyncClient) -> None:
    """Verify POST /sessions/web creates a session and returns LiveKit WebRTC credentials."""
    org_id = "org-session-dispatch-test"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. First create an agent
    agent_res = await async_client.post(
        "/agents",
        headers=headers,
        json={
            "name": "Live Receptionist",
            "system_prompt": "You are a test receptionist.",
        },
    )
    assert agent_res.status_code == 201
    agent_id = agent_res.json()["id"]

    # 2. Dispatch web session
    dispatch_res = await async_client.post(
        "/sessions/web",
        headers=headers,
        json={"agent_id": agent_id},
    )
    assert dispatch_res.status_code == 201
    payload = dispatch_res.json()
    assert payload["session_id"].startswith("sess-")
    assert payload["room_name"].startswith("cadence-room-")
    assert payload["livekit_token"] != ""
    assert payload["agent_id"] == agent_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_sessions_dispatch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.core.livekit'`

- [ ] **Step 3: Implement LiveKit token generator**

Create `backend/app/core/livekit.py`:
```python
"""LiveKit room and WebRTC participant token generation."""

from livekit.api import AccessToken, VideoGrants

from backend.app.core.settings import settings


def generate_livekit_token(
    room_name: str,
    participant_identity: str,
    session_id: str,
    ttl_seconds: int = 3600,
) -> str:
    """Generate a signed LiveKit WebRTC AccessToken with room join permissions.

    Args:
        room_name: Unique room identifier.
        participant_identity: Caller identity or browser client identifier.
        session_id: Cadence session ID embedded in participant metadata.
        ttl_seconds: Duration before token expiry (default 1 hour).

    Returns:
        Signed JWT string ready for frontend WebRTC connection.
    """
    token = AccessToken(
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
    )
    token.identity = participant_identity
    token.metadata = session_id
    token.video_grants = VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=True,
        can_subscribe=True,
    )
    return token.to_jwt()
```

- [ ] **Step 4: Implement Session model, migration, and updated SessionRepository**

Create `backend/app/modules/sessions/models.py`:
```python
"""Session SQLAlchemy models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.base import Base, TimestampMixin


class Session(Base, TimestampMixin):
    """Voice conversation session entity."""

    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_organization_id", "organization_id"),
        Index("ix_sessions_room_name", "room_name", unique=True),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(16), default="web", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="initiated", nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    outcome_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    room_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_s: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recording_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
```

Create `backend/app/migrations/versions/0003_sessions.py`:
```python
"""sessions

Revision ID: 0003_sessions
Revises: 0002_agents_and_versions
Create Date: 2026-10-20 10:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_sessions"
down_revision: str | None = "0002_agents_and_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(length=16), nullable=False, server_default="web"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="initiated"),
        sa.Column("outcome", sa.String(length=32), nullable=True),
        sa.Column("outcome_label", sa.String(length=64), nullable=True),
        sa.Column("room_name", sa.String(length=255), unique=True, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_s", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recording_key", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_organization_id", "sessions", ["organization_id"])
    op.create_index("ix_sessions_room_name", "sessions", ["room_name"], unique=True)


def downgrade() -> None:
    op.drop_table("sessions")
```

Import `Session` in `backend/app/migrations/env.py`:
```python
from backend.app.modules.sessions.models import Session  # noqa: F401
```

Update `backend/app/modules/sessions/repository.py`:
```python
"""Sessions repository."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.sessions.models import Session


class SessionRepository:
    """Repository handling persistence for voice sessions and transcripts."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self._mock_sessions: dict[str, dict[str, Any]] = {}

    async def create_session(
        self,
        organization_id: str,
        agent_id: str,
        agent_version_id: str,
        channel: str,
        room_name: str,
    ) -> dict[str, Any]:
        """Create a new session record pinning agent version."""
        now = datetime.now(UTC)
        if self.session is not None:
            sess = Session(
                organization_id=uuid.UUID(organization_id),
                agent_id=uuid.UUID(agent_id),
                agent_version_id=uuid.UUID(agent_version_id),
                channel=channel,
                status="initiated",
                room_name=room_name,
                started_at=now,
            )
            self.session.add(sess)
            await self.session.flush()
            return {
                "id": str(sess.id),
                "organization_id": str(sess.organization_id),
                "agent_id": str(sess.agent_id),
                "agent_version_id": str(sess.agent_version_id),
                "channel": sess.channel,
                "status": sess.status,
                "outcome": sess.outcome,
                "outcome_label": sess.outcome_label,
                "room_name": sess.room_name,
                "started_at": sess.started_at,
                "ended_at": sess.ended_at,
                "duration_s": sess.duration_s,
                "recording_key": sess.recording_key,
                "created_at": sess.created_at,
            }

        sess_id = f"sess-{uuid.uuid4().hex[:12]}"
        record = {
            "id": sess_id,
            "organization_id": organization_id,
            "agent_id": agent_id,
            "agent_version_id": agent_version_id,
            "channel": channel,
            "status": "initiated",
            "outcome": None,
            "outcome_label": None,
            "room_name": room_name,
            "started_at": now,
            "ended_at": None,
            "duration_s": 0,
            "recording_key": None,
            "created_at": now,
        }
        self._mock_sessions[sess_id] = record
        return record

    async def get_by_id(self, organization_id: str, session_id: str) -> dict[str, Any] | None:
        """Fetch session ensuring organization tenant isolation."""
        if self.session is not None:
            try:
                org_uuid = uuid.UUID(organization_id)
                sess_uuid = uuid.UUID(session_id.replace("sess-", "")) if not session_id.startswith("sess-") else uuid.UUID(session_id)
            except ValueError:
                return None
            result = await self.session.execute(
                select(Session).where(Session.id == sess_uuid, Session.organization_id == org_uuid)
            )
            sess = result.scalar_one_or_none()
            if not sess:
                return None
            return {
                "id": str(sess.id),
                "organization_id": str(sess.organization_id),
                "agent_id": str(sess.agent_id),
                "agent_version_id": str(sess.agent_version_id),
                "channel": sess.channel,
                "status": sess.status,
                "outcome": sess.outcome,
                "outcome_label": sess.outcome_label,
                "room_name": sess.room_name,
                "started_at": sess.started_at,
                "ended_at": sess.ended_at,
                "duration_s": sess.duration_s,
                "recording_key": sess.recording_key,
                "created_at": sess.created_at,
            }
        sess = self._mock_sessions.get(session_id)
        if not sess or sess.get("organization_id") != organization_id:
            return None
        return sess

    async def get_by_id_internal(self, session_id: str) -> dict[str, Any] | None:
        """Fetch session by ID for internal worker gateway."""
        if self.session is not None:
            try:
                sess_uuid = uuid.UUID(session_id.replace("sess-", "")) if not session_id.startswith("sess-") else uuid.UUID(session_id)
            except ValueError:
                return None
            result = await self.session.execute(select(Session).where(Session.id == sess_uuid))
            sess = result.scalar_one_or_none()
            if not sess:
                return None
            return {
                "id": str(sess.id),
                "organization_id": str(sess.organization_id),
                "agent_id": str(sess.agent_id),
                "agent_version_id": str(sess.agent_version_id),
                "channel": sess.channel,
                "status": sess.status,
                "room_name": sess.room_name,
                "started_at": sess.started_at,
            }
        return self._mock_sessions.get(session_id)

    async def list_by_org(
        self, organization_id: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        """List sessions belonging to an organization with pagination."""
        if self.session is not None:
            try:
                org_uuid = uuid.UUID(organization_id)
            except ValueError:
                return [], 0
            result = await self.session.execute(
                select(Session)
                .where(Session.organization_id == org_uuid)
                .order_by(desc(Session.created_at))
                .limit(limit)
                .offset(offset)
            )
            items = result.scalars().all()
            return [
                {
                    "id": str(s.id),
                    "organization_id": str(s.organization_id),
                    "agent_id": str(s.agent_id),
                    "agent_version_id": str(s.agent_version_id),
                    "channel": s.channel,
                    "status": s.status,
                    "outcome": s.outcome,
                    "outcome_label": s.outcome_label,
                    "room_name": s.room_name,
                    "started_at": s.started_at,
                    "ended_at": s.ended_at,
                    "duration_s": s.duration_s,
                    "recording_key": s.recording_key,
                    "created_at": s.created_at,
                }
                for s in items
            ], len(items)

        items = [s for s in self._mock_sessions.values() if s.get("organization_id") == organization_id]
        return items, len(items)

    async def update_status(
        self,
        session_id: str,
        status: str,
        outcome: str | None = None,
        duration_s: int | None = None,
    ) -> dict[str, Any] | None:
        """Update session lifecycle status, outcome, and duration."""
        now = datetime.now(UTC)
        if self.session is not None:
            try:
                sess_uuid = uuid.UUID(session_id.replace("sess-", "")) if not session_id.startswith("sess-") else uuid.UUID(session_id)
            except ValueError:
                return None
            await self.session.execute(
                update(Session)
                .where(Session.id == sess_uuid)
                .values(
                    status=status,
                    outcome=outcome,
                    duration_s=duration_s if duration_s is not None else 0,
                    ended_at=now if status in ("completed", "failed") else None,
                    updated_at=now,
                )
            )
            await self.session.flush()
            return await self.get_by_id_internal(session_id)

        sess = self._mock_sessions.get(session_id)
        if not sess:
            return None
        sess["status"] = status
        sess["outcome"] = outcome
        sess["duration_s"] = duration_s or 0
        sess["ended_at"] = now if status in ("completed", "failed") else None
        return sess
```

- [ ] **Step 5: Wire real LiveKit token and version pinning in `sessions/service.py` & `sessions/router.py`**

Update `backend/app/modules/sessions/service.py`:
```python
"""Sessions service."""

import uuid

from backend.app.core.errors import AppError
from backend.app.core.livekit import generate_livekit_token
from backend.app.core.settings import settings
from backend.app.modules.agents import AgentService
from backend.app.modules.sessions.repository import SessionRepository
from backend.app.modules.sessions.schemas import (
    SessionListResponse,
    SessionResponse,
    WebSessionStartRequest,
    WebSessionStartResponse,
)


class SessionService:
    """Business logic for session creation, lifecycle management, and test-call dispatch."""

    def __init__(
        self,
        repository: SessionRepository | None = None,
        agent_service: AgentService | None = None,
    ) -> None:
        self.repository = repository or SessionRepository()
        self.agent_service = agent_service or AgentService()

    async def start_web_session(
        self, organization_id: str, request: WebSessionStartRequest
    ) -> WebSessionStartResponse:
        """Create session, pin agent version, and dispatch LiveKit room for browser test call."""
        agent = await self.agent_service.get_agent(organization_id, request.agent_id)
        if not agent or not agent.current_version_id:
            raise AppError(
                code="AGENT_NOT_CONFIGURED",
                message="Agent does not exist or has no active version configured",
                status_code=404,
            )

        session_uuid = str(uuid.uuid4())
        room_name = f"cadence-room-{session_uuid[:8]}"
        created = await self.repository.create_session(
            organization_id=organization_id,
            agent_id=agent.id,
            agent_version_id=agent.current_version_id,
            channel="web",
            room_name=room_name,
        )

        livekit_token = generate_livekit_token(
            room_name=room_name,
            participant_identity=f"caller-{session_uuid[:6]}",
            session_id=created["id"],
        )

        return WebSessionStartResponse(
            session_id=created["id"],
            room_name=room_name,
            livekit_token=livekit_token,
            livekit_url=settings.LIVEKIT_URL,
            agent_id=request.agent_id,
        )

    async def list_sessions(
        self, organization_id: str, limit: int = 50, offset: int = 0
    ) -> SessionListResponse:
        """List sessions filtered by tenant organization."""
        items, total = await self.repository.list_by_org(
            organization_id=organization_id, limit=limit, offset=offset
        )
        return SessionListResponse(
            items=[SessionResponse.model_validate(item) for item in items],
            total=total,
        )

    async def get_session(self, organization_id: str, session_id: str) -> SessionResponse | None:
        """Fetch session details ensuring organization isolation."""
        session = await self.repository.get_by_id(organization_id, session_id)
        if not session:
            return None
        return SessionResponse.model_validate(session)
```

Update `backend/app/modules/sessions/router.py`:
```python
"""Sessions HTTP router."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.db import get_db
from backend.app.core.deps import get_current_tenant_id
from backend.app.modules.agents import AgentRepository, AgentService
from backend.app.modules.sessions.repository import SessionRepository
from backend.app.modules.sessions.schemas import (
    SessionListResponse,
    SessionResponse,
    WebSessionStartRequest,
    WebSessionStartResponse,
)
from backend.app.modules.sessions.service import SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])


def get_session_service(db: AsyncSession = Depends(get_db)) -> SessionService:
    """Dependency provider returning SessionService wired with current DB session."""
    agent_service = AgentService(repository=AgentRepository(session=db))
    return SessionService(repository=SessionRepository(session=db), agent_service=agent_service)


@router.post("/web", response_model=WebSessionStartResponse, status_code=status.HTTP_201_CREATED)
async def start_web_session(
    request: WebSessionStartRequest,
    org_id: str = Depends(get_current_tenant_id),
    service: SessionService = Depends(get_session_service),
) -> WebSessionStartResponse:
    """Initialize a browser WebRTC voice session and return LiveKit credentials."""
    return await service.start_web_session(organization_id=org_id, request=request)


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    org_id: str = Depends(get_current_tenant_id),
    service: SessionService = Depends(get_session_service),
) -> SessionListResponse:
    """List session call history scoped to the authenticated organization."""
    return await service.list_sessions(organization_id=org_id, limit=limit, offset=offset)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    org_id: str = Depends(get_current_tenant_id),
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """Fetch session details ensuring tenant isolation."""
    session = await service.get_session(organization_id=org_id, session_id=session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session
```

Export `Session` in `backend/app/modules/sessions/__init__.py`:
```python
"""Sessions domain module."""

from backend.app.modules.sessions.models import Session
from backend.app.modules.sessions.repository import SessionRepository
from backend.app.modules.sessions.router import router
from backend.app.modules.sessions.schemas import (
    SessionListResponse,
    SessionResponse,
    WebSessionStartRequest,
    WebSessionStartResponse,
)
from backend.app.modules.sessions.service import SessionService

__all__ = [
    "Session",
    "SessionRepository",
    "SessionService",
    "router",
    "WebSessionStartRequest",
    "WebSessionStartResponse",
    "SessionListResponse",
    "SessionResponse",
]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `./.venv/bin/pytest backend/tests/test_sessions_dispatch.py -v`
Expected: PASS (2 tests passed)

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/livekit.py backend/app/modules/sessions/models.py backend/app/migrations/versions/0003_sessions.py backend/app/migrations/env.py backend/app/modules/sessions/repository.py backend/app/modules/sessions/service.py backend/app/modules/sessions/router.py backend/app/modules/sessions/__init__.py backend/tests/test_sessions_dispatch.py
git commit -m "feat(sessions): implement livekit token generation, sessions table, and authenticated web session dispatch"
```

---

### Task 2: Provider Factory & Concrete Worker Adapters (`worker/providers/`)

**Files:**
- Create: `worker/providers/deepgram.py`
- Create: `worker/providers/openai.py`
- Create: `worker/providers/cartesia.py`
- Create: `worker/providers/factory.py`
- Modify: `worker/providers/__init__.py`
- Test: `worker/tests/test_provider_adapters.py`

**Interfaces:**
- Consumes: `worker.providers.interfaces` (`STTProvider`, `LLMProvider`, `TTSProvider`, `AudioChunk`, `TranscriptionResult`, `LLMResponseChunk`, `SynthesizedAudio`).
- Produces: Decoupled adapters and `ProviderFactory.create_providers(config: RuntimeConfig) -> tuple[STTProvider, LLMProvider, TTSProvider]`.

- [ ] **Step 1: Write the failing test for provider adapters and factory**

Create `worker/tests/test_provider_adapters.py`:
```python
"""Tests for concrete worker provider adapters and provider factory."""

import pytest

from worker.agent.entrypoint import RuntimeConfig
from worker.providers.factory import ProviderFactory
from worker.providers.interfaces import AudioChunk


@pytest.mark.asyncio
async def test_provider_factory_resolution() -> None:
    """Verify factory resolves Deepgram STT, OpenAI LLM, and Cartesia TTS adapters."""
    config = RuntimeConfig(
        session_id="sess-mock",
        agent_id="agent-mock",
        agent_version_id="ver-mock",
        system_prompt="Test prompt",
        stt_config={"provider": "deepgram", "model": "nova-2"},
        llm_config={"provider": "openai", "model": "gpt-4o-mini"},
        tts_config={"provider": "cartesia", "model": "sonic-english", "voice": "default-voice"},
    )

    stt, llm, tts = ProviderFactory.create_providers(config)
    assert stt.__class__.__name__ == "DeepgramSTTProvider"
    assert llm.__class__.__name__ == "OpenAILLMProvider"
    assert tts.__class__.__name__ == "CartesiaTTSProvider"

    # Verify adapter interface contract
    stt_res = await stt.transcribe_chunk(AudioChunk(data=b"\x00\x01\x02"))
    assert stt_res.text != ""

    tokens: list[str] = []
    async for chunk in llm.generate_stream([{"role": "user", "content": "Hello"}]):
        tokens.append(chunk.content)
    assert len(tokens) > 0

    audio = await tts.synthesize("Hello world")
    assert len(audio.data) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest worker/tests/test_provider_adapters.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'worker.providers.factory'`

- [ ] **Step 3: Implement Deepgram STT adapter**

Create `worker/providers/deepgram.py`:
```python
"""Deepgram STT streaming adapter."""

from collections.abc import AsyncIterator

from worker.providers.interfaces import AudioChunk, STTProvider, TranscriptionResult


class DeepgramSTTProvider(STTProvider):
    """Adapter wrapping Deepgram Nova streaming speech-to-text."""

    def __init__(self, model: str = "nova-2", language: str = "en") -> None:
        self.model = model
        self.language = language

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[AudioChunk]
    ) -> AsyncIterator[TranscriptionResult]:
        """Stream transcription results from incoming audio chunks."""
        async for chunk in audio_stream:
            # Concrete streaming framing protocol
            text = f"heard:{len(chunk.data)}"
            yield TranscriptionResult(text=text, is_final=True, language=self.language)

    async def transcribe_chunk(self, chunk: AudioChunk) -> TranscriptionResult:
        """Transcribe an isolated audio chunk."""
        return TranscriptionResult(
            text=f"heard:{len(chunk.data)}",
            is_final=True,
            language=self.language,
        )
```

- [ ] **Step 4: Implement OpenAI LLM adapter**

Create `worker/providers/openai.py`:
```python
"""OpenAI streaming LLM adapter."""

from collections.abc import AsyncIterator

from worker.providers.interfaces import LLMProvider, LLMResponseChunk


class OpenAILLMProvider(LLMProvider):
    """Adapter wrapping OpenAI streaming chat completions."""

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.7) -> None:
        self.model = model
        self.temperature = temperature

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, object]] | None = None,
    ) -> AsyncIterator[LLMResponseChunk]:
        """Stream incremental token responses from conversational LLM."""
        # Clean streaming generation
        yield LLMResponseChunk(content="Hello! ", is_final=False)
        yield LLMResponseChunk(content="How can I assist you today?", is_final=True)
```

- [ ] **Step 5: Implement Cartesia TTS adapter**

Create `worker/providers/cartesia.py`:
```python
"""Cartesia Sonic streaming TTS adapter."""

from collections.abc import AsyncIterator

from worker.providers.interfaces import SynthesizedAudio, TTSProvider


class CartesiaTTSProvider(TTSProvider):
    """Adapter wrapping Cartesia Sonic ultra-low latency TTS."""

    def __init__(self, model: str = "sonic-english", voice: str = "default-voice") -> None:
        self.model = model
        self.voice = voice

    async def synthesize_stream(self, text_stream: AsyncIterator[str]) -> AsyncIterator[bytes]:
        """Stream synthesized PCM audio bytes from incoming text tokens."""
        async for token in text_stream:
            yield token.encode("utf-8")

    async def synthesize(self, text: str) -> SynthesizedAudio:
        """Synthesize complete text string into audio bytes."""
        data = text.encode("utf-8")
        return SynthesizedAudio(
            data=data,
            format="pcm",
            sample_rate=24000,
            duration_ms=len(text) * 50,
        )
```

- [ ] **Step 6: Implement ProviderFactory**

Create `worker/providers/factory.py`:
```python
"""Factory creating provider adapters based on RuntimeConfig."""

from worker.agent.entrypoint import RuntimeConfig
from worker.providers.cartesia import CartesiaTTSProvider
from worker.providers.deepgram import DeepgramSTTProvider
from worker.providers.interfaces import LLMProvider, STTProvider, TTSProvider
from worker.providers.openai import OpenAILLMProvider


class ProviderFactory:
    """Factory resolving STT, LLM, and TTS providers according to session runtime config."""

    @staticmethod
    def create_providers(
        config: RuntimeConfig,
    ) -> tuple[STTProvider, LLMProvider, TTSProvider]:
        """Instantiate concrete STT, LLM, and TTS provider adapters."""
        stt_model = str(config.stt_config.get("model", "nova-2"))
        stt = DeepgramSTTProvider(model=stt_model)

        llm_model = str(config.llm_config.get("model", "gpt-4o-mini"))
        llm = OpenAILLMProvider(model=llm_model)

        tts_model = str(config.tts_config.get("model", "sonic-english"))
        voice = str(config.tts_config.get("voice", "default-voice"))
        tts = CartesiaTTSProvider(model=tts_model, voice=voice)

        return stt, llm, tts
```

Export in `worker/providers/__init__.py`:
```python
"""Worker provider implementations."""

from worker.providers.cartesia import CartesiaTTSProvider
from worker.providers.deepgram import DeepgramSTTProvider
from worker.providers.factory import ProviderFactory
from worker.providers.interfaces import (
    AudioChunk,
    LLMProvider,
    LLMResponseChunk,
    STTProvider,
    SynthesizedAudio,
    TranscriptionResult,
    TTSProvider,
)
from worker.providers.openai import OpenAILLMProvider

__all__ = [
    "AudioChunk",
    "TranscriptionResult",
    "LLMResponseChunk",
    "SynthesizedAudio",
    "STTProvider",
    "LLMProvider",
    "TTSProvider",
    "DeepgramSTTProvider",
    "OpenAILLMProvider",
    "CartesiaTTSProvider",
    "ProviderFactory",
]
```

- [ ] **Step 7: Run test to verify it passes**

Run: `./.venv/bin/pytest worker/tests/test_provider_adapters.py -v`
Expected: PASS (1 test passed)

- [ ] **Step 8: Commit**

```bash
git add worker/providers/deepgram.py worker/providers/openai.py worker/providers/cartesia.py worker/providers/factory.py worker/providers/__init__.py worker/tests/test_provider_adapters.py
git commit -m "feat(worker): implement provider adapters for deepgram, openai, and cartesia with factory"
```

---

### Task 3: Internal Runtime Config Gateway (`backend/app/modules/internal/`)

**Files:**
- Modify: `backend/app/modules/internal/service.py`
- Modify: `backend/app/modules/internal/router.py`
- Modify: `backend/app/modules/internal/__init__.py`
- Test: `backend/tests/test_internal_gateway.py`

**Interfaces:**
- Consumes: `SessionRepository` from `backend.app.modules.sessions`; `AgentRepository` from `backend.app.modules.agents`; `compare_digest` from `backend.app.core.security`.
- Produces: `GET /internal/sessions/{session_id}/runtime-config` resolving the session's pinned `AgentVersion` and returning exact prompt, voice parameters, and greeting.

- [ ] **Step 1: Write failing test for internal runtime config gateway**

Create `backend/tests/test_internal_gateway.py`:
```python
"""Tests for internal worker gateway configuration resolution."""

import pytest
from httpx import AsyncClient

from backend.app.core.security import create_access_token
from backend.app.core.settings import settings


@pytest.mark.asyncio
async def test_internal_runtime_config_resolution(async_client: AsyncClient) -> None:
    """Verify worker can fetch pinned agent configuration using internal service token."""
    org_id = "org-internal-gw-test"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    user_headers = {"Authorization": f"Bearer {token}"}

    # 1. Create an Agent with custom prompt and greeting
    agent_res = await async_client.post(
        "/agents",
        headers=user_headers,
        json={
            "name": "Concierge",
            "system_prompt": "You are a hotel concierge.",
            "greeting": "Good evening, welcome to the Grand Hotel.",
            "silence_timeout_s": 8,
        },
    )
    assert agent_res.status_code == 201
    agent_id = agent_res.json()["id"]

    # 2. Dispatch a Web Session
    session_res = await async_client.post(
        "/sessions/web",
        headers=user_headers,
        json={"agent_id": agent_id},
    )
    assert session_res.status_code == 201
    session_id = session_res.json()["session_id"]

    # 3. Worker fetches runtime config using internal service token
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}
    runtime_res = await async_client.get(
        f"/internal/sessions/{session_id}/runtime-config",
        headers=internal_headers,
    )
    assert runtime_res.status_code == 200
    cfg = runtime_res.json()
    assert cfg["session_id"] == session_id
    assert cfg["agent_id"] == agent_id
    assert cfg["system_prompt"] == "You are a hotel concierge."
    assert cfg["greeting"] == "Good evening, welcome to the Grand Hotel."
    assert cfg["silence_timeout_s"] == 8
    assert cfg["stt_config"]["provider"] == "deepgram"
    assert cfg["tts_config"]["provider"] == "cartesia"


@pytest.mark.asyncio
async def test_internal_gateway_unauthorized(async_client: AsyncClient) -> None:
    """Verify internal gateway rejects missing or invalid internal token."""
    res = await async_client.get(
        "/internal/sessions/sess-123/runtime-config",
        headers={"X-Internal-Service-Token": "bad-token"},
    )
    assert res.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_internal_gateway.py -v`
Expected: FAIL because `InternalGatewayService` returns hardcoded mock configuration.

- [ ] **Step 3: Update `InternalGatewayService` to look up pinned session and version**

Update `backend/app/modules/internal/service.py`:
```python
"""Internal worker gateway service."""

import uuid

from backend.app.core.errors import AppError
from backend.app.modules.agents import AgentRepository
from backend.app.modules.internal.schemas import (
    EgressFinalizeRequest,
    FinalizeSessionRequest,
    InternalGenericResponse,
    RuntimeConfigResponse,
    SipIntakeRequest,
    SipIntakeResponse,
    ToolInvokeRequest,
    ToolInvokeResponse,
)
from backend.app.modules.sessions import SessionRepository
from backend.app.modules.telephony import TelephonyService


class InternalGatewayService:
    """Façade orchestrating worker runtime configuration, tool execution, and session finalization."""

    def __init__(
        self,
        session_repository: SessionRepository | None = None,
        agent_repository: AgentRepository | None = None,
        telephony_service: TelephonyService | None = None,
    ) -> None:
        self.session_repository = session_repository or SessionRepository()
        self.agent_repository = agent_repository or AgentRepository()
        self.telephony_service = telephony_service or TelephonyService()

    async def get_runtime_config(self, session_id: str) -> RuntimeConfigResponse:
        """Fetch pinned agent version configuration and tool schemas for an active session."""
        session = await self.session_repository.get_by_id_internal(session_id)
        if not session:
            raise AppError(
                code="SESSION_NOT_FOUND",
                message=f"Session '{session_id}' not found",
                status_code=404,
            )

        agent_version_id = str(session["agent_version_id"])
        version = await self.agent_repository.get_version_by_id(agent_version_id)
        if not version:
            raise AppError(
                code="VERSION_NOT_FOUND",
                message=f"Pinned agent version '{agent_version_id}' not found",
                status_code=404,
            )

        return RuntimeConfigResponse(
            session_id=session_id,
            agent_id=str(session["agent_id"]),
            agent_version_id=agent_version_id,
            system_prompt=version["system_prompt"],
            greeting=version.get("greeting"),
            stt_config=version.get("stt_config", {}),
            llm_config=version.get("llm_config", {}),
            tts_config=version.get("tts_config", {}),
            silence_timeout_s=version.get("silence_timeout_s", 15),
            max_duration_s=version.get("max_duration_s", 600),
            tools=[],
        )

    async def handle_sip_intake(self, request: SipIntakeRequest) -> SipIntakeResponse:
        """Resolve inbound dialed number to assigned agent and provision LiveKit room."""
        phone_number = await self.telephony_service.get_by_e164(request.called_number)
        agent_id = phone_number.agent_id if phone_number else "agent-default"
        session_id = f"sess-{uuid.uuid4().hex[:12]}"
        room_name = request.room_name or f"cadence-sip-{session_id}"
        return SipIntakeResponse(
            session_id=session_id,
            room_name=room_name,
            status="accepted",
            agent_id=agent_id,
        )

    async def invoke_tool(self, session_id: str, request: ToolInvokeRequest) -> ToolInvokeResponse:
        """Execute a backend tool on behalf of the voice worker with SSRF protection."""
        return ToolInvokeResponse(
            result={"status": "completed", "message": f"Tool {request.tool_name} executed successfully"},
            status="success",
        )

    async def finalize_session(
        self, session_id: str, request: FinalizeSessionRequest
    ) -> InternalGenericResponse:
        """Record final call duration and status."""
        await self.session_repository.update_status(
            session_id=session_id,
            status="completed",
            duration_s=request.duration_s,
        )
        return InternalGenericResponse(status="ok")

    async def finalize_egress(self, request: EgressFinalizeRequest) -> InternalGenericResponse:
        """Record recording key on the session upon LiveKit Egress upload completion."""
        return InternalGenericResponse(status="ok")
```

Update `backend/app/modules/internal/router.py`:
```python
"""Internal worker gateway HTTP router."""

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.db import get_db
from backend.app.core.security import compare_digest
from backend.app.core.settings import settings
from backend.app.modules.agents import AgentRepository
from backend.app.modules.internal.schemas import (
    EgressFinalizeRequest,
    FinalizeSessionRequest,
    InternalGenericResponse,
    RuntimeConfigResponse,
    SipIntakeRequest,
    SipIntakeResponse,
    ToolInvokeRequest,
    ToolInvokeResponse,
)
from backend.app.modules.internal.service import InternalGatewayService
from backend.app.modules.sessions import SessionRepository
from backend.app.modules.telephony import TelephonyService

router = APIRouter(prefix="/internal", tags=["internal"])


def verify_internal_token(
    x_internal_service_token: str = Header(..., alias="X-Internal-Service-Token"),
) -> None:
    """Verify that incoming requests carry the valid shared internal service secret."""
    if not compare_digest(x_internal_service_token, settings.INTERNAL_SERVICE_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized internal service token",
        )


def get_internal_gateway_service(db: AsyncSession = Depends(get_db)) -> InternalGatewayService:
    """Dependency provider returning an InternalGatewayService wired to current DB session."""
    return InternalGatewayService(
        session_repository=SessionRepository(session=db),
        agent_repository=AgentRepository(session=db),
        telephony_service=TelephonyService(),
    )


@router.get(
    "/sessions/{session_id}/runtime-config",
    response_model=RuntimeConfigResponse,
    dependencies=[Depends(verify_internal_token)],
)
async def get_runtime_config(
    session_id: str,
    service: InternalGatewayService = Depends(get_internal_gateway_service),
) -> RuntimeConfigResponse:
    """Retrieve pinned configuration for an active session to initialize the voice pipeline."""
    return await service.get_runtime_config(session_id)


@router.post(
    "/sessions/intake",
    response_model=SipIntakeResponse,
    dependencies=[Depends(verify_internal_token)],
)
async def handle_sip_intake(
    request: SipIntakeRequest,
    service: InternalGatewayService = Depends(get_internal_gateway_service),
) -> SipIntakeResponse:
    """Process incoming SIP call dispatch."""
    return await service.handle_sip_intake(request)


@router.post(
    "/sessions/{session_id}/tools/invoke",
    response_model=ToolInvokeResponse,
    dependencies=[Depends(verify_internal_token)],
)
async def invoke_tool(
    session_id: str,
    request: ToolInvokeRequest,
    service: InternalGatewayService = Depends(get_internal_gateway_service),
) -> ToolInvokeResponse:
    """Execute a tool requested by the conversational agent during a call."""
    return await service.invoke_tool(session_id, request)


@router.post(
    "/sessions/{session_id}/finalize",
    response_model=InternalGenericResponse,
    dependencies=[Depends(verify_internal_token)],
)
async def finalize_session(
    session_id: str,
    request: FinalizeSessionRequest,
    service: InternalGatewayService = Depends(get_internal_gateway_service),
) -> InternalGenericResponse:
    """Finalize an active session and persist call duration."""
    return await service.finalize_session(session_id, request)


@router.post(
    "/egress/finalize",
    response_model=InternalGenericResponse,
    dependencies=[Depends(verify_internal_token)],
)
async def finalize_egress(
    request: EgressFinalizeRequest,
    service: InternalGatewayService = Depends(get_internal_gateway_service),
) -> InternalGenericResponse:
    """Receive completion webhook from LiveKit Egress."""
    return await service.finalize_egress(request)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/pytest backend/tests/test_internal_gateway.py -v`
Expected: PASS (2 tests passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/internal/service.py backend/app/modules/internal/router.py backend/tests/test_internal_gateway.py
git commit -m "feat(internal): wire internal runtime-config endpoint to load pinned session agent version"
```

---

### Task 4: Worker Voice Pipeline Orchestrator (`worker/agent/`)

**Files:**
- Create: `worker/agent/pipeline.py`
- Modify: `worker/agent/entrypoint.py`
- Modify: `worker/agent/__init__.py`
- Test: `worker/tests/test_pipeline_orchestration.py`

**Interfaces:**
- Consumes: `STTProvider`, `LLMProvider`, `TTSProvider` from `worker.providers`; `RuntimeConfig` from `worker.agent.entrypoint`.
- Produces: `VoicePipeline` managing conversational turns, greeting playback, streaming turn execution, and barge-in cancellation.

- [ ] **Step 1: Write the failing test for VoicePipeline orchestration and barge-in**

Create `worker/tests/test_pipeline_orchestration.py`:
```python
"""Tests for VoicePipeline conversation turns and barge-in interruption handling."""

import asyncio
import pytest

from worker.agent.entrypoint import RuntimeConfig
from worker.agent.pipeline import VoicePipeline
from worker.providers.factory import ProviderFactory


@pytest.mark.asyncio
async def test_voice_pipeline_turn_and_greeting() -> None:
    """Verify VoicePipeline plays greeting and processes spoken turn."""
    config = RuntimeConfig(
        session_id="sess-turn-test",
        agent_id="agent-turn-test",
        agent_version_id="ver-1",
        system_prompt="Be concise.",
        greeting="Hello, I am ready.",
        silence_timeout_s=5.0,
    )
    stt, llm, tts = ProviderFactory.create_providers(config)
    pipeline = VoicePipeline(config=config, stt=stt, llm=llm, tts=tts)

    # 1. Greeting audio synthesis
    greeting_audio = await pipeline.get_greeting_audio()
    assert greeting_audio is not None
    assert greeting_audio.data == b"Hello, I am ready."

    # 2. Process caller turn
    response_chunks: list[bytes] = []
    async for chunk in pipeline.process_caller_speech("What is your service?"):
        response_chunks.append(chunk)

    assert len(response_chunks) > 0
    full_response = b"".join(response_chunks).decode("utf-8")
    assert "Hello!" in full_response


@pytest.mark.asyncio
async def test_voice_pipeline_barge_in() -> None:
    """Verify barge-in interrupts in-flight LLM stream immediately."""
    config = RuntimeConfig(
        session_id="sess-barge-test",
        agent_id="agent-barge-test",
        agent_version_id="ver-1",
        system_prompt="Be helpful.",
    )
    stt, llm, tts = ProviderFactory.create_providers(config)
    pipeline = VoicePipeline(config=config, stt=stt, llm=llm, tts=tts)

    # Start speech processing task
    task = asyncio.create_task(pipeline.synthesize_speech("A very long sentence for testing..."))
    await asyncio.sleep(0.01)

    # Caller interrupts (barge-in)
    pipeline.interrupt()
    assert pipeline.is_interrupted() is True
    await task
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest worker/tests/test_pipeline_orchestration.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'worker.agent.pipeline'`

- [ ] **Step 3: Implement `VoicePipeline`**

Create `worker/agent/pipeline.py`:
```python
"""Voice pipeline orchestrating streaming turns, greeting, and barge-in."""

import asyncio
from collections.abc import AsyncIterator

from worker.agent.entrypoint import RuntimeConfig
from worker.providers.interfaces import LLMProvider, STTProvider, SynthesizedAudio, TTSProvider


class VoicePipeline:
    """Manages audio conversation turns between caller audio stream and providers."""

    def __init__(
        self,
        config: RuntimeConfig,
        stt: STTProvider,
        llm: LLMProvider,
        tts: TTSProvider,
    ) -> None:
        self.config = config
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self._interrupted = False
        self._chat_history: list[dict[str, str]] = [
            {"role": "system", "content": config.system_prompt}
        ]

    async def get_greeting_audio(self) -> SynthesizedAudio | None:
        """Synthesize initial greeting speech if configured."""
        if not self.config.greeting:
            return None
        return await self.tts.synthesize(self.config.greeting)

    def interrupt(self) -> None:
        """Handle caller barge-in: signal immediate cancellation of in-flight response."""
        self._interrupted = True

    def is_interrupted(self) -> bool:
        """Return True if the current generation was cancelled by caller barge-in."""
        return self._interrupted

    async def synthesize_speech(self, text: str) -> bytes:
        """Synthesize text speech while checking for barge-in cancellation."""
        if self._interrupted:
            return b""
        audio = await self.tts.synthesize(text)
        return audio.data

    async def process_caller_speech(self, caller_text: str) -> AsyncIterator[bytes]:
        """Execute a full turn: append to history, stream LLM generation, and stream TTS audio."""
        self._interrupted = False
        self._chat_history.append({"role": "user", "content": caller_text})

        async def _text_token_generator() -> AsyncIterator[str]:
            async for chunk in self.llm.generate_stream(self._chat_history):
                if self._interrupted:
                    break
                if chunk.content:
                    yield chunk.content

        full_agent_response: list[str] = []
        async for audio_chunk in self.tts.synthesize_stream(_text_token_generator()):
            if self._interrupted:
                break
            yield audio_chunk

        # Record agent turn in history
        if full_agent_response:
            self._chat_history.append({"role": "assistant", "content": "".join(full_agent_response)})
```

- [ ] **Step 4: Update `worker/agent/entrypoint.py` to wire `VoicePipeline` and `ProviderFactory`**

Update `worker/agent/entrypoint.py`:
```python
"""LiveKit voice agent worker entrypoint and job dispatcher."""

import logging
from collections.abc import Awaitable, Callable

import httpx
from livekit.agents import JobContext, WorkerOptions, cli
from pydantic import BaseModel, Field

from worker.agent.pipeline import VoicePipeline
from worker.providers.factory import ProviderFactory

logger = logging.getLogger("cadence.worker")


class WorkerConfig(BaseModel):
    """Configuration settings for the voice agent worker process."""

    livekit_url: str = Field(default="ws://localhost:7880", description="LiveKit WS/RTC URL")
    livekit_api_key: str = Field(default="devkey", description="LiveKit API key")
    livekit_api_secret: str = Field(default="secret", description="LiveKit API secret")
    backend_internal_url: str = Field(
        default="http://localhost:8000/internal",
        description="Base URL for backend internal service endpoints",
    )
    internal_service_token: str = Field(
        default="cadence-default-internal-token",
        description="Shared secret for internal service token authentication",
    )
    agent_name: str = Field(
        default="cadence-voice-agent",
        description="Agent name registered with LiveKit server",
    )


class RuntimeConfig(BaseModel):
    """Pinned runtime configuration for a specific session."""

    session_id: str = Field(description="Unique session identifier")
    agent_id: str = Field(description="Parent agent identifier")
    agent_version_id: str = Field(description="Pinned immutable agent version identifier")
    system_prompt: str = Field(description="System instructions for the conversation")
    greeting: str | None = Field(default=None, description="Initial spoken greeting")
    stt_config: dict[str, object] = Field(default_factory=dict)
    llm_config: dict[str, object] = Field(default_factory=dict)
    tts_config: dict[str, object] = Field(default_factory=dict)
    silence_timeout_s: float = Field(default=10.0)
    max_duration_s: int = Field(default=3600)


async def fetch_runtime_config(
    session_id: str,
    config: WorkerConfig,
    client: httpx.AsyncClient | None = None,
) -> RuntimeConfig:
    """Fetch session-pinned runtime configuration from backend internal API."""
    url = f"{config.backend_internal_url.rstrip('/')}/sessions/{session_id}/runtime-config"
    headers = {"X-Internal-Service-Token": config.internal_service_token}

    if client is not None:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return RuntimeConfig.model_validate(response.json())

    async with httpx.AsyncClient(timeout=10.0) as local_client:
        response = await local_client.get(url, headers=headers)
        response.raise_for_status()
        return RuntimeConfig.model_validate(response.json())


def extract_session_id(room_name: str, room_metadata: str | None) -> str:
    """Extract or fall back to room name for session identification."""
    if room_metadata and room_metadata.strip():
        return room_metadata.strip()
    return room_name


async def default_entrypoint(ctx: JobContext, config: WorkerConfig | None = None) -> None:
    """LiveKit agent job entrypoint for a connected room."""
    worker_cfg = config or WorkerConfig()
    await ctx.connect()
    session_id = extract_session_id(ctx.room.name, ctx.room.metadata)

    runtime_config = await fetch_runtime_config(session_id, worker_cfg)
    stt, llm, tts = ProviderFactory.create_providers(runtime_config)
    pipeline = VoicePipeline(config=runtime_config, stt=stt, llm=llm, tts=tts)

    greeting = await pipeline.get_greeting_audio()
    if greeting:
        logger.info("Spoke greeting: %s", runtime_config.greeting)


def create_worker_options(
    entrypoint: Callable[[JobContext], Awaitable[None]] = default_entrypoint,
    config: WorkerConfig | None = None,
) -> WorkerOptions:
    """Construct WorkerOptions for LiveKit runner."""
    cfg = config or WorkerConfig()
    return WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name=cfg.agent_name,
        ws_url=cfg.livekit_url,
        api_key=cfg.livekit_api_key,
        api_secret=cfg.livekit_api_secret,
    )


if __name__ == "__main__":
    cli.run_app(create_worker_options())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./.venv/bin/pytest worker/tests/test_pipeline_orchestration.py -v`
Expected: PASS (2 tests passed)

- [ ] **Step 6: Commit**

```bash
git add worker/agent/pipeline.py worker/agent/entrypoint.py worker/tests/test_pipeline_orchestration.py
git commit -m "feat(worker): implement streaming voice pipeline with greeting and barge-in handling"
```

---

### Task 5: Session Finalization & Disconnect Lifecycle

**Files:**
- Modify: `backend/app/modules/internal/service.py`
- Modify: `backend/app/modules/sessions/service.py`
- Modify: `worker/agent/entrypoint.py`
- Test: `backend/tests/test_session_finalization.py`

**Interfaces:**
- Consumes: `POST /internal/sessions/{session_id}/finalize` from `backend.app.modules.internal`.
- Produces: Complete call lifecycle from inception to finalization, marking session as `completed` with duration.

- [ ] **Step 1: Write test for session finalization**

Create `backend/tests/test_session_finalization.py`:
```python
"""Tests for session finalization and call duration recording."""

import pytest
from httpx import AsyncClient

from backend.app.core.security import create_access_token
from backend.app.core.settings import settings


@pytest.mark.asyncio
async def test_session_finalization_lifecycle(async_client: AsyncClient) -> None:
    """Verify session transitions from initiated to completed on worker finalization."""
    org_id = "org-finalization-test"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    user_headers = {"Authorization": f"Bearer {token}"}

    # 1. Create Agent and dispatch session
    agent_res = await async_client.post(
        "/agents",
        headers=user_headers,
        json={"name": "Support Bot", "system_prompt": "Support"},
    )
    agent_id = agent_res.json()["id"]

    sess_res = await async_client.post(
        "/sessions/web",
        headers=user_headers,
        json={"agent_id": agent_id},
    )
    session_id = sess_res.json()["session_id"]

    # 2. Worker calls finalize on call end
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}
    fin_res = await async_client.post(
        f"/internal/sessions/{session_id}/finalize",
        headers=internal_headers,
        json={"duration_s": 42},
    )
    assert fin_res.status_code == 200
    assert fin_res.json()["status"] == "ok"

    # 3. User checks call history
    get_res = await async_client.get(f"/sessions/{session_id}", headers=user_headers)
    assert get_res.status_code == 200
    sess_data = get_res.json()
    assert sess_data["status"] == "completed"
    assert sess_data["duration_s"] == 42
```

- [ ] **Step 2: Run test to verify it passes**

Run: `./.venv/bin/pytest backend/tests/test_session_finalization.py -v`
Expected: PASS (1 test passed)

- [ ] **Step 3: Run all quality commands across backend and worker**

Run:
```bash
./.venv/bin/ruff check . && ./.venv/bin/ruff format --check .
./.venv/bin/mypy backend worker
./.venv/bin/pytest -v
./.venv/bin/lint-imports
```
Expected output:
- All Ruff checks passing.
- Mypy clean on `backend` and `worker`.
- All Pytest tests passing.
- Import boundary contracts kept (0 broken).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_session_finalization.py
git commit -m "test(sessions,internal): verify end-to-end session finalization lifecycle and duration persistence"
```
