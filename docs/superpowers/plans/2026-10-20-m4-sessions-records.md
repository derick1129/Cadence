# Milestone M4: Sessions & Records Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish complete, trustworthy, immutable call records including ordered transcript turns, stage latency metrics, audio recording management with presigned access, and background session reconciliation.

**Architecture:** Layered domain monolith with asynchronous persistence. The `sessions` module owns `sessions`, `transcript_segments`, and `session_metrics` tables. The worker transmits completed turn transcripts and turn latencies to `/internal/sessions/{id}/finalize`. LiveKit Egress uploads audio to S3/MinIO and fires a signed webhook (`/internal/egress/finalize`) to associate `recording_key`. Customers retrieve paginated call histories, full transcripts, latency metrics, and time-limited presigned S3 audio URLs strictly scoped to their tenant context.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (asyncio, asyncpg), Alembic, HMAC-SHA256 SigV4 (S3/MinIO presigned URLs), Pytest, Import-Linter.

## Global Constraints

- Never commit directly to `main`; work on short-lived feature branch `feat/m4-sessions-records`.
- Every Python file must be fully type-annotated (`mypy` strict mode without `Any` unless justified).
- Standard JSON error shape for API: `{"error": {"code": "...", "message": "...", "details": ...}}`.
- Never hard-delete sessions, transcripts, or usage records; use soft status fields (`completed`, `failed`).
- Repositories refuse to run tenant queries without an explicit `organization_id`.
- S3/MinIO signed URLs must be short-lived (default 15 minutes) and verify tenant ownership before issuance.
- No PII (phone numbers, full caller audio paths, raw transcripts) logged at `INFO` level or above.
- Quality commands must pass before commit:
  - `ruff check . && ruff format --check .`
  - `mypy backend worker`
  - `pytest -q`
  - `lint-imports`

---

### Task 1: Database ORM Models (`TranscriptSegment`, `SessionMetric`) & Migration `0004_sessions_records`

**Files:**
- Modify: `backend/app/modules/sessions/models.py`
- Create: `backend/app/migrations/versions/0004_sessions_records.py`
- Modify: `backend/app/modules/sessions/__init__.py`
- Modify: `backend/app/migrations/env.py`
- Test: `backend/tests/test_sessions_records_models.py`

**Interfaces:**
- Consumes: `Base`, `TimestampMixin` from `backend.app.core.base`; `Session` from `backend.app.modules.sessions.models`.
- Produces:
  - `TranscriptSegment`: `id`, `session_id` (FK to sessions.id ON DELETE CASCADE), `seq`, `speaker` ("caller" or "agent"), `text`, `started_at_ms`, `created_at`.
  - `SessionMetric`: `id`, `session_id` (FK to sessions.id ON DELETE CASCADE, UNIQUE), `avg_latency_ms`, `p95_latency_ms`, `interruption_count`, `llm_tokens_used`, `stt_seconds_billed`, `tts_characters_billed`, `created_at`.

- [ ] **Step 1: Write the failing test for TranscriptSegment and SessionMetric models**

Create `backend/tests/test_sessions_records_models.py`:
```python
"""Tests for TranscriptSegment and SessionMetric SQLAlchemy ORM models."""

import uuid

from backend.app.modules.sessions.models import SessionMetric, TranscriptSegment


def test_transcript_segment_model() -> None:
    """Verify TranscriptSegment model attributes, sequence ordering, and speaker types."""
    session_id = uuid.uuid4()
    segment = TranscriptSegment(
        session_id=session_id,
        seq=1,
        speaker="caller",
        text="Hello, I want to book an appointment.",
        started_at_ms=1200,
    )
    assert segment.session_id == session_id
    assert segment.seq == 1
    assert segment.speaker == "caller"
    assert segment.text == "Hello, I want to book an appointment."
    assert segment.started_at_ms == 1200
    assert isinstance(segment.id, uuid.UUID)


def test_session_metric_model() -> None:
    """Verify SessionMetric model attributes, latency metrics, and token counters."""
    session_id = uuid.uuid4()
    metrics = SessionMetric(
        session_id=session_id,
        avg_latency_ms=320,
        p95_latency_ms=640,
        interruption_count=1,
        llm_tokens_used=450,
        stt_seconds_billed=18.5,
        tts_characters_billed=210,
    )
    assert metrics.session_id == session_id
    assert metrics.avg_latency_ms == 320
    assert metrics.p95_latency_ms == 640
    assert metrics.interruption_count == 1
    assert metrics.llm_tokens_used == 450
    assert metrics.stt_seconds_billed == 18.5
    assert metrics.tts_characters_billed == 210
    assert isinstance(metrics.id, uuid.UUID)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_sessions_records_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'TranscriptSegment' from 'backend.app.modules.sessions.models'`

- [ ] **Step 3: Implement TranscriptSegment and SessionMetric in `sessions/models.py`**

Update `backend/app/modules/sessions/models.py`:
```python
"""Session, TranscriptSegment, and SessionMetric SQLAlchemy models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
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


class TranscriptSegment(Base, TimestampMixin):
    """Individual spoken dialogue segment recorded during a voice session."""

    __tablename__ = "transcript_segments"
    __table_args__ = (
        Index("ix_transcript_segments_session_seq", "session_id", "seq"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(16), nullable=False)  # "caller" or "agent"
    text: Mapped[str] = mapped_column(Text, nullable=False)
    started_at_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SessionMetric(Base, TimestampMixin):
    """Aggregate latency, token usage, and quality metrics for a voice session."""

    __tablename__ = "session_metrics"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_session_metrics_session_id"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    avg_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    p95_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interruption_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    llm_tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stt_seconds_billed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    tts_characters_billed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
```

Export new models in `backend/app/modules/sessions/__init__.py`:
```python
"""Sessions domain module."""

from backend.app.modules.sessions.models import Session, SessionMetric, TranscriptSegment
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
    "TranscriptSegment",
    "SessionMetric",
    "SessionRepository",
    "SessionService",
    "router",
    "WebSessionStartRequest",
    "WebSessionStartResponse",
    "SessionListResponse",
    "SessionResponse",
]
```

Import in `backend/app/migrations/env.py`:
```python
from backend.app.modules.sessions.models import Session, SessionMetric, TranscriptSegment  # noqa: F401
```

- [ ] **Step 4: Create migration `0004_sessions_records.py`**

Create `backend/app/migrations/versions/0004_sessions_records.py`:
```python
"""sessions_records

Revision ID: 0004_sessions_records
Revises: 0003_sessions
Create Date: 2026-10-20 16:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_sessions_records"
down_revision: str | None = "0003_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transcript_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("started_at_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_transcript_segments_session_seq", "transcript_segments", ["session_id", "seq"])

    op.create_table(
        "session_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("avg_latency_ms", sa.Integer(), nullable=True),
        sa.Column("p95_latency_ms", sa.Integer(), nullable=True),
        sa.Column("interruption_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stt_seconds_billed", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tts_characters_billed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", name="uq_session_metrics_session_id"),
    )


def downgrade() -> None:
    op.drop_table("session_metrics")
    op.drop_table("transcript_segments")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/bin/pytest backend/tests/test_sessions_records_models.py -v`
Expected: PASS (2 tests passed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/sessions/models.py backend/app/modules/sessions/__init__.py backend/app/migrations/env.py backend/app/migrations/versions/0004_sessions_records.py backend/tests/test_sessions_records_models.py
git commit -m "feat(sessions): add transcript_segments and session_metrics models with alembic migration"
```

---

### Task 2: S3/MinIO Audio Storage Helper (`backend/app/core/storage.py`)

**Files:**
- Create: `backend/app/core/storage.py`
- Modify: `backend/app/core/__init__.py`
- Test: `backend/tests/test_storage.py`

**Interfaces:**
- Consumes: `settings.S3_ENDPOINT`, `settings.S3_ACCESS_KEY`, `settings.S3_SECRET_KEY`, `settings.S3_RECORDINGS_BUCKET`.
- Produces: `generate_presigned_s3_url(key: str, expires_in_seconds: int = 900, method: str = "GET") -> str`. Pure Python AWS SigV4 implementation with zero external dependencies.

- [ ] **Step 1: Write the failing test for presigned S3 URL generation**

Create `backend/tests/test_storage.py`:
```python
"""Tests for S3/MinIO presigned URL generator with AWS Signature Version 4."""

from urllib.parse import parse_qs, urlparse

from backend.app.core.storage import generate_presigned_s3_url


def test_generate_presigned_s3_url() -> None:
    """Verify presigned S3 URL contains required SigV4 query parameters and signature."""
    key = "recordings/org-123/sess-456.mp4"
    url = generate_presigned_s3_url(key=key, expires_in_seconds=600)

    parsed = urlparse(url)
    assert parsed.scheme in ("http", "https")
    assert key in parsed.path

    query_params = parse_qs(parsed.query)
    assert "X-Amz-Algorithm" in query_params
    assert query_params["X-Amz-Algorithm"][0] == "AWS4-HMAC-SHA256"
    assert "X-Amz-Credential" in query_params
    assert "X-Amz-Date" in query_params
    assert "X-Amz-Expires" in query_params
    assert query_params["X-Amz-Expires"][0] == "600"
    assert "X-Amz-Signature" in query_params
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.core.storage'`

- [ ] **Step 3: Implement SigV4 S3 presigned URL generator in `core/storage.py`**

Create `backend/app/core/storage.py`:
```python
"""S3/MinIO object storage presigned URL generation via AWS Signature Version 4."""

import hashlib
import hmac
from datetime import UTC, datetime
from urllib.parse import quote, urlparse

from backend.app.core.settings import settings


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    """Compute HMAC-SHA256 digest."""
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _get_signature_key(key: str, date_stamp: str, region_name: str, service_name: str) -> bytes:
    """Derive AWS SigV4 signing key."""
    k_date = _hmac_sha256(f"AWS4{key}".encode("utf-8"), date_stamp)
    k_region = _hmac_sha256(k_date, region_name)
    k_service = _hmac_sha256(k_region, service_name)
    return _hmac_sha256(k_service, "aws4_request")


def generate_presigned_s3_url(
    key: str,
    bucket: str | None = None,
    expires_in_seconds: int = 900,
    method: str = "GET",
) -> str:
    """Generate an AWS SigV4 presigned URL for S3/MinIO object retrieval or upload."""
    bucket_name = bucket or settings.S3_RECORDINGS_BUCKET
    endpoint = settings.S3_ENDPOINT.rstrip("/")
    access_key = settings.S3_ACCESS_KEY
    secret_key = settings.S3_SECRET_KEY
    region = "us-east-1"
    service = "s3"

    parsed_endpoint = urlparse(endpoint)
    host = parsed_endpoint.netloc

    now = datetime.now(UTC)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    clean_key = key.lstrip("/")
    canonical_uri = f"/{bucket_name}/{clean_key}"

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    credential_param = f"{access_key}/{credential_scope}"

    query_params = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": credential_param,
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(expires_in_seconds),
        "X-Amz-SignedHeaders": "host",
    }

    sorted_params = sorted(query_params.items())
    canonical_query = "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in sorted_params)
    canonical_headers = f"host:{host}\n"
    signed_headers = "host"
    payload_hash = "UNSIGNED-PAYLOAD"

    canonical_request = (
        f"{method}\n{canonical_uri}\n{canonical_query}\n"
        f"{canonical_headers}\n{signed_headers}\n{payload_hash}"
    )

    string_to_sign = (
        f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )

    signing_key = _get_signature_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    return f"{endpoint}{canonical_uri}?{canonical_query}&X-Amz-Signature={signature}"
```

Export in `backend/app/core/__init__.py`:
```python
from backend.app.core.storage import generate_presigned_s3_url

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
    "storage",
    "generate_presigned_s3_url",
    "AppError",
    "app_error_handler",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest backend/tests/test_storage.py -v`
Expected: PASS (1 test passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/storage.py backend/app/core/__init__.py backend/tests/test_storage.py
git commit -m "feat(core): implement aws sigv4 presigned s3 url generator for recordings"
```

---

### Task 3: Session Repository Transcript, Metrics & Enhanced Filtering Queries

**Files:**
- Modify: `backend/app/modules/sessions/repository.py`
- Test: `backend/tests/test_sessions_records_repository.py`

**Interfaces:**
- Consumes: `Session`, `TranscriptSegment`, `SessionMetric` models; `AsyncSession` from `sqlalchemy.ext.asyncio`.
- Produces: `SessionRepository` methods (`create_transcript_segments`, `get_transcript`, `create_or_update_metrics`, `get_metrics`, `update_recording_key`).

- [ ] **Step 1: Write the failing repository test**

Create `backend/tests/test_sessions_records_repository.py`:
```python
"""Tests for SessionRepository transcript, metrics, and recording persistence."""

import uuid
import pytest

from backend.app.modules.sessions.repository import SessionRepository


@pytest.mark.asyncio
async def test_session_repository_records_lifecycle() -> None:
    """Verify persisting and querying transcript segments, metrics, and recording keys."""
    repo = SessionRepository()
    org_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())

    # 1. Create Session
    sess = await repo.create_session(
        organization_id=org_id,
        agent_id=agent_id,
        agent_version_id=version_id,
        channel="web",
        room_name=f"test-room-{uuid.uuid4().hex[:6]}",
    )
    session_id = sess["id"]

    # 2. Add Transcript Segments
    segments = [
        {"seq": 1, "speaker": "agent", "text": "Hello, how can I help?", "started_at_ms": 0},
        {"seq": 2, "speaker": "caller", "text": "I need support.", "started_at_ms": 2100},
    ]
    saved_segments = await repo.create_transcript_segments(session_id, segments)
    assert len(saved_segments) == 2

    # Fetch transcript
    retrieved = await repo.get_transcript(session_id)
    assert len(retrieved) == 2
    assert retrieved[0]["text"] == "Hello, how can I help?"
    assert retrieved[1]["speaker"] == "caller"

    # 3. Add Session Metrics
    metrics_data = {
        "avg_latency_ms": 280,
        "p95_latency_ms": 520,
        "interruption_count": 0,
        "llm_tokens_used": 150,
        "stt_seconds_billed": 8.0,
        "tts_characters_billed": 45,
    }
    saved_metrics = await repo.create_or_update_metrics(session_id, metrics_data)
    assert saved_metrics["avg_latency_ms"] == 280

    retrieved_metrics = await repo.get_metrics(session_id)
    assert retrieved_metrics is not None
    assert retrieved_metrics["p95_latency_ms"] == 520

    # 4. Update Recording Key
    updated_sess = await repo.update_recording_key(session_id, "recordings/call-123.mp4")
    assert updated_sess is not None
    assert updated_sess["recording_key"] == "recordings/call-123.mp4"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_sessions_records_repository.py -v`
Expected: FAIL because `SessionRepository` does not have `create_transcript_segments`.

- [ ] **Step 3: Implement transcript, metrics, and recording queries in `SessionRepository`**

Update `backend/app/modules/sessions/repository.py` by adding:
```python
    async def create_transcript_segments(
        self, session_id: str, segments: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Persist ordered transcript segments for a session."""
        now = datetime.now(UTC)
        if self.session is not None:
            sess_uuid = uuid.UUID(session_id.replace("sess-", "")) if not session_id.startswith("sess-") else uuid.UUID(session_id)
            records: list[TranscriptSegment] = []
            for s in segments:
                item = TranscriptSegment(
                    session_id=sess_uuid,
                    seq=int(s["seq"]),
                    speaker=str(s["speaker"]),
                    text=str(s["text"]),
                    started_at_ms=int(s.get("started_at_ms", 0)),
                )
                self.session.add(item)
                records.append(item)
            await self.session.flush()
            return [
                {
                    "id": str(r.id),
                    "session_id": str(r.session_id),
                    "seq": r.seq,
                    "speaker": r.speaker,
                    "text": r.text,
                    "started_at_ms": r.started_at_ms,
                    "created_at": r.created_at,
                }
                for r in records
            ]

        res = []
        for s in segments:
            rec = {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "seq": s["seq"],
                "speaker": s["speaker"],
                "text": s["text"],
                "started_at_ms": s.get("started_at_ms", 0),
                "created_at": now,
            }
            res.append(rec)
        self._mock_transcripts.setdefault(session_id, []).extend(res)
        return res

    async def get_transcript(self, session_id: str) -> list[dict[str, Any]]:
        """Retrieve ordered transcript segments for a session."""
        if self.session is not None:
            try:
                sess_uuid = uuid.UUID(session_id.replace("sess-", "")) if not session_id.startswith("sess-") else uuid.UUID(session_id)
            except ValueError:
                return []
            result = await self.session.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.session_id == sess_uuid)
                .order_by(TranscriptSegment.seq.asc())
            )
            records = result.scalars().all()
            return [
                {
                    "id": str(r.id),
                    "session_id": str(r.session_id),
                    "seq": r.seq,
                    "speaker": r.speaker,
                    "text": r.text,
                    "started_at_ms": r.started_at_ms,
                    "created_at": r.created_at,
                }
                for r in records
            ]
        items = self._mock_transcripts.get(session_id, [])
        return sorted(items, key=lambda x: int(x["seq"]))

    async def create_or_update_metrics(
        self, session_id: str, metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """Persist or update turn latency and token metrics for a session."""
        now = datetime.now(UTC)
        if self.session is not None:
            sess_uuid = uuid.UUID(session_id.replace("sess-", "")) if not session_id.startswith("sess-") else uuid.UUID(session_id)
            metric_item = SessionMetric(
                session_id=sess_uuid,
                avg_latency_ms=metrics.get("avg_latency_ms"),
                p95_latency_ms=metrics.get("p95_latency_ms"),
                interruption_count=metrics.get("interruption_count", 0),
                llm_tokens_used=metrics.get("llm_tokens_used", 0),
                stt_seconds_billed=float(metrics.get("stt_seconds_billed", 0.0)),
                tts_characters_billed=int(metrics.get("tts_characters_billed", 0)),
            )
            self.session.add(metric_item)
            await self.session.flush()
            return {
                "id": str(metric_item.id),
                "session_id": str(metric_item.session_id),
                "avg_latency_ms": metric_item.avg_latency_ms,
                "p95_latency_ms": metric_item.p95_latency_ms,
                "interruption_count": metric_item.interruption_count,
                "llm_tokens_used": metric_item.llm_tokens_used,
                "stt_seconds_billed": metric_item.stt_seconds_billed,
                "tts_characters_billed": metric_item.tts_characters_billed,
                "created_at": metric_item.created_at,
            }
        rec = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "avg_latency_ms": metrics.get("avg_latency_ms"),
            "p95_latency_ms": metrics.get("p95_latency_ms"),
            "interruption_count": metrics.get("interruption_count", 0),
            "llm_tokens_used": metrics.get("llm_tokens_used", 0),
            "stt_seconds_billed": metrics.get("stt_seconds_billed", 0.0),
            "tts_characters_billed": metrics.get("tts_characters_billed", 0),
            "created_at": now,
        }
        self._mock_metrics[session_id] = rec
        return rec

    async def get_metrics(self, session_id: str) -> dict[str, Any] | None:
        """Fetch session metrics by session ID."""
        if self.session is not None:
            try:
                sess_uuid = uuid.UUID(session_id.replace("sess-", "")) if not session_id.startswith("sess-") else uuid.UUID(session_id)
            except ValueError:
                return None
            result = await self.session.execute(
                select(SessionMetric).where(SessionMetric.session_id == sess_uuid)
            )
            m = result.scalar_one_or_none()
            if not m:
                return None
            return {
                "id": str(m.id),
                "session_id": str(m.session_id),
                "avg_latency_ms": m.avg_latency_ms,
                "p95_latency_ms": m.p95_latency_ms,
                "interruption_count": m.interruption_count,
                "llm_tokens_used": m.llm_tokens_used,
                "stt_seconds_billed": m.stt_seconds_billed,
                "tts_characters_billed": m.tts_characters_billed,
                "created_at": m.created_at,
            }
        return self._mock_metrics.get(session_id)

    async def update_recording_key(
        self, session_id: str, recording_key: str
    ) -> dict[str, Any] | None:
        """Update session with object storage recording key."""
        if self.session is not None:
            try:
                sess_uuid = uuid.UUID(session_id.replace("sess-", "")) if not session_id.startswith("sess-") else uuid.UUID(session_id)
            except ValueError:
                return None
            await self.session.execute(
                update(Session)
                .where(Session.id == sess_uuid)
                .values(recording_key=recording_key, updated_at=datetime.now(UTC))
            )
            await self.session.flush()
            return await self.get_by_id_internal(session_id)
        sess = self._mock_sessions.get(session_id)
        if not sess:
            return None
        sess["recording_key"] = recording_key
        return sess
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest backend/tests/test_sessions_records_repository.py -v`
Expected: PASS (1 test passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/sessions/repository.py backend/tests/test_sessions_records_repository.py
git commit -m "feat(sessions): add transcript, metrics, and recording methods to session repository"
```

---

### Task 4: Worker Gateway Session Finalization & Egress Webhook (`internal` module)

**Files:**
- Modify: `backend/app/modules/internal/schemas.py`
- Modify: `backend/app/modules/internal/service.py`
- Modify: `backend/app/modules/internal/router.py`
- Test: `backend/tests/test_internal_records_finalization.py`

**Interfaces:**
- Consumes: `SessionRepository` from `backend.app.modules.sessions`.
- Produces:
  - `POST /internal/sessions/{id}/finalize`: accepts structured transcript turns and metrics, persisting all records in one atomic transaction.
  - `POST /internal/egress/finalize`: accepts LiveKit Egress completion webhooks and attaches `recording_key`.

- [ ] **Step 1: Write the failing test for internal records finalization**

Create `backend/tests/test_internal_records_finalization.py`:
```python
"""Tests for internal worker finalization with full transcript and metrics recording."""

import pytest
from httpx import AsyncClient

from backend.app.core.security import create_access_token
from backend.app.core.settings import settings


@pytest.mark.asyncio
async def test_internal_finalization_with_transcripts_and_metrics(async_client: AsyncClient) -> None:
    """Verify worker can finalize session with transcripts, metrics, and outcome."""
    org_id = "org-records-test"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    user_headers = {"Authorization": f"Bearer {token}"}

    # 1. Create Agent and Web Session
    agent_res = await async_client.post(
        "/agents",
        headers=user_headers,
        json={"name": "Support Agent", "system_prompt": "Help users."},
    )
    agent_id = agent_res.json()["id"]

    sess_res = await async_client.post(
        "/sessions/web",
        headers=user_headers,
        json={"agent_id": agent_id},
    )
    session_id = sess_res.json()["session_id"]
    room_name = sess_res.json()["room_name"]

    # 2. Worker calls /finalize with transcripts and metrics
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}
    finalize_payload = {
        "duration_s": 55,
        "status": "completed",
        "outcome": "completed",
        "outcome_label": "resolved",
        "transcript_segments": [
            {"seq": 1, "speaker": "caller", "text": "What are your business hours?", "started_at_ms": 1000},
            {"seq": 2, "speaker": "agent", "text": "We are open from 9am to 5pm daily.", "started_at_ms": 2500},
        ],
        "metrics": {
            "avg_latency_ms": 310,
            "p95_latency_ms": 580,
            "interruption_count": 0,
            "llm_tokens_used": 120,
            "stt_seconds_billed": 6.5,
            "tts_characters_billed": 38,
        },
    }
    fin_res = await async_client.post(
        f"/internal/sessions/{session_id}/finalize",
        headers=internal_headers,
        json=finalize_payload,
    )
    assert fin_res.status_code == 200

    # 3. LiveKit Egress calls /egress/finalize
    egress_res = await async_client.post(
        "/internal/egress/finalize",
        headers=internal_headers,
        json={
            "room_name": room_name,
            "recording_key": f"recordings/{session_id}.mp4",
        },
    )
    assert egress_res.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_internal_records_finalization.py -v`
Expected: FAIL because `FinalizeSessionRequest` doesn't support transcripts and metrics.

- [ ] **Step 3: Update `FinalizeSessionRequest` schema**

Update `backend/app/modules/internal/schemas.py`:
```python
"""Internal worker gateway schemas."""

from typing import Any
from pydantic import BaseModel, Field


class TranscriptSegmentInput(BaseModel):
    """Dialogue turn input from worker finalization."""

    seq: int
    speaker: str
    text: str
    started_at_ms: int = 0


class SessionMetricsInput(BaseModel):
    """Aggregate metrics reported by worker on call conclusion."""

    avg_latency_ms: int | None = None
    p95_latency_ms: int | None = None
    interruption_count: int = 0
    llm_tokens_used: int = 0
    stt_seconds_billed: float = 0.0
    tts_characters_billed: int = 0


class FinalizeSessionRequest(BaseModel):
    """Payload to finalize an active session with transcripts and metrics."""

    duration_s: int = Field(ge=0, description="Call duration in seconds")
    status: str = "completed"
    outcome: str | None = None
    outcome_label: str | None = None
    transcript_segments: list[TranscriptSegmentInput] = Field(default_factory=list)
    metrics: SessionMetricsInput | None = None


class EgressFinalizeRequest(BaseModel):
    """Payload from LiveKit Egress completion webhook."""

    recording_key: str = Field(description="S3 object key for the call audio recording")
    room_name: str | None = None
    session_id: str | None = None
```

- [ ] **Step 4: Update `InternalGatewayService.finalize_session` & `finalize_egress`**

In `backend/app/modules/internal/service.py`:
```python
    async def finalize_session(
        self, session_id: str, request: FinalizeSessionRequest
    ) -> InternalGenericResponse:
        """Persist transcript segments, turn metrics, and update session status."""
        await self.session_repository.update_status(
            session_id=session_id,
            status=request.status,
            outcome=request.outcome,
            duration_s=request.duration_s,
        )

        if request.transcript_segments:
            segments_data = [s.model_dump() for s in request.transcript_segments]
            await self.session_repository.create_transcript_segments(session_id, segments_data)

        if request.metrics:
            await self.session_repository.create_or_update_metrics(
                session_id, request.metrics.model_dump()
            )

        return InternalGenericResponse(status="ok")

    async def finalize_egress(self, request: EgressFinalizeRequest) -> InternalGenericResponse:
        """Record recording key on the session upon LiveKit Egress upload completion."""
        session_id = request.session_id
        if not session_id and request.room_name:
            sess = await self.session_repository.get_by_room_name(request.room_name)
            if sess:
                session_id = sess["id"]

        if session_id:
            await self.session_repository.update_recording_key(session_id, request.recording_key)

        return InternalGenericResponse(status="ok")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./.venv/bin/pytest backend/tests/test_internal_records_finalization.py -v`
Expected: PASS (1 test passed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/internal/schemas.py backend/app/modules/internal/service.py backend/tests/test_internal_records_finalization.py
git commit -m "feat(internal): support transcripts, metrics, and egress recording key in session finalization"
```

---

### Task 5: Customer HTTP API: Transcript, Metrics, Recording Presigned URL, and Filtering

**Files:**
- Modify: `backend/app/modules/sessions/schemas.py`
- Modify: `backend/app/modules/sessions/service.py`
- Modify: `backend/app/modules/sessions/router.py`
- Test: `backend/tests/test_sessions_records_api.py`

**Interfaces:**
- Consumes: `SessionRepository`, `generate_presigned_s3_url`, `get_current_tenant_id`.
- Produces:
  - `GET /sessions/{id}/transcript`: returns list of transcript turns.
  - `GET /sessions/{id}/metrics`: returns latency and token counters.
  - `GET /sessions/{id}/recording-url`: returns `{ "recording_url": "...", "expires_in": 900 }`.

- [ ] **Step 1: Write the failing API test for records endpoints**

Create `backend/tests/test_sessions_records_api.py`:
```python
"""Tests for customer-facing transcript, metrics, and recording presigned URL endpoints."""

import pytest
from httpx import AsyncClient

from backend.app.core.security import create_access_token
from backend.app.core.settings import settings


@pytest.mark.asyncio
async def test_customer_records_endpoints(async_client: AsyncClient) -> None:
    """Verify customer can retrieve session transcripts, metrics, and presigned recording URLs."""
    org_id = "org-records-api-test"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    user_headers = {"Authorization": f"Bearer {token}"}
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    # 1. Create Agent and Session
    agent_res = await async_client.post(
        "/agents",
        headers=user_headers,
        json={"name": "Billing Agent", "system_prompt": "Help with bills."},
    )
    agent_id = agent_res.json()["id"]

    sess_res = await async_client.post(
        "/sessions/web",
        headers=user_headers,
        json={"agent_id": agent_id},
    )
    session_id = sess_res.json()["session_id"]

    # 2. Finalize session with transcript & recording
    await async_client.post(
        f"/internal/sessions/{session_id}/finalize",
        headers=internal_headers,
        json={
            "duration_s": 30,
            "transcript_segments": [
                {"seq": 1, "speaker": "caller", "text": "I paid my bill.", "started_at_ms": 1000},
                {"seq": 2, "speaker": "agent", "text": "Thank you, payment confirmed.", "started_at_ms": 3000},
            ],
            "metrics": {"avg_latency_ms": 250, "p95_latency_ms": 400},
        },
    )
    await async_client.post(
        "/internal/egress/finalize",
        headers=internal_headers,
        json={"session_id": session_id, "recording_key": f"recordings/{session_id}.mp4"},
    )

    # 3. Retrieve Transcript
    trans_res = await async_client.get(f"/sessions/{session_id}/transcript", headers=user_headers)
    assert trans_res.status_code == 200
    trans_data = trans_res.json()
    assert len(trans_data) == 2
    assert trans_data[0]["speaker"] == "caller"
    assert trans_data[1]["text"] == "Thank you, payment confirmed."

    # 4. Retrieve Metrics
    metrics_res = await async_client.get(f"/sessions/{session_id}/metrics", headers=user_headers)
    assert metrics_res.status_code == 200
    metrics_data = metrics_res.json()
    assert metrics_data["avg_latency_ms"] == 250

    # 5. Retrieve Recording URL
    rec_res = await async_client.get(f"/sessions/{session_id}/recording-url", headers=user_headers)
    assert rec_res.status_code == 200
    assert "recording_url" in rec_res.json()
    assert f"recordings/{session_id}.mp4" in rec_res.json()["recording_url"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_sessions_records_api.py -v`
Expected: FAIL (404 Not Found on `/transcript`).

- [ ] **Step 3: Update `sessions/schemas.py`, `service.py`, and `router.py`**

In `backend/app/modules/sessions/schemas.py`:
```python
class TranscriptSegmentResponse(BaseModel):
    """Spoken dialogue turn response."""

    id: str
    session_id: str
    seq: int
    speaker: str
    text: str
    started_at_ms: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionMetricResponse(BaseModel):
    """Aggregate session latency and usage metrics response."""

    id: str
    session_id: str
    avg_latency_ms: int | None = None
    p95_latency_ms: int | None = None
    interruption_count: int = 0
    llm_tokens_used: int = 0
    stt_seconds_billed: float = 0.0
    tts_characters_billed: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecordingUrlResponse(BaseModel):
    """Presigned time-limited access URL for call audio playback."""

    recording_url: str
    expires_in_seconds: int = 900
```

In `backend/app/modules/sessions/service.py`:
```python
    async def get_transcript(
        self, organization_id: str, session_id: str
    ) -> list[TranscriptSegmentResponse]:
        """Fetch transcript segments ensuring tenant isolation."""
        session = await self.get_session(organization_id, session_id)
        if not session:
            raise AppError(code="SESSION_NOT_FOUND", message="Session not found", status_code=404)
        items = await self.repository.get_transcript(session_id)
        return [TranscriptSegmentResponse.model_validate(i) for i in items]

    async def get_metrics(
        self, organization_id: str, session_id: str
    ) -> SessionMetricResponse | None:
        """Fetch session metrics ensuring tenant isolation."""
        session = await self.get_session(organization_id, session_id)
        if not session:
            raise AppError(code="SESSION_NOT_FOUND", message="Session not found", status_code=404)
        data = await self.repository.get_metrics(session_id)
        if not data:
            return None
        return SessionMetricResponse.model_validate(data)

    async def get_recording_url(
        self, organization_id: str, session_id: str
    ) -> RecordingUrlResponse:
        """Generate presigned S3/MinIO playback URL after validating tenant ownership."""
        session = await self.get_session(organization_id, session_id)
        if not session:
            raise AppError(code="SESSION_NOT_FOUND", message="Session not found", status_code=404)
        if not session.recording_key:
            raise AppError(code="RECORDING_NOT_FOUND", message="No recording exists for this session", status_code=404)

        from backend.app.core.storage import generate_presigned_s3_url
        url = generate_presigned_s3_url(key=session.recording_key, expires_in_seconds=900)
        return RecordingUrlResponse(recording_url=url, expires_in_seconds=900)
```

In `backend/app/modules/sessions/router.py`:
```python
@router.get("/{session_id}/transcript", response_model=list[TranscriptSegmentResponse])
async def get_session_transcript(
    session_id: str,
    org_id: str = Depends(get_current_tenant_id),
    service: SessionService = Depends(get_session_service),
) -> list[TranscriptSegmentResponse]:
    """Retrieve ordered transcript segments for a call."""
    return await service.get_transcript(organization_id=org_id, session_id=session_id)


@router.get("/{session_id}/metrics", response_model=SessionMetricResponse | None)
async def get_session_metrics(
    session_id: str,
    org_id: str = Depends(get_current_tenant_id),
    service: SessionService = Depends(get_session_service),
) -> SessionMetricResponse | None:
    """Retrieve turn latency and token usage metrics for a call."""
    return await service.get_metrics(organization_id=org_id, session_id=session_id)


@router.get("/{session_id}/recording-url", response_model=RecordingUrlResponse)
async def get_recording_url(
    session_id: str,
    org_id: str = Depends(get_current_tenant_id),
    service: SessionService = Depends(get_session_service),
) -> RecordingUrlResponse:
    """Get a short-lived presigned URL to stream or download call audio recording."""
    return await service.get_recording_url(organization_id=org_id, session_id=session_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest backend/tests/test_sessions_records_api.py -v`
Expected: PASS (1 test passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/sessions/schemas.py backend/app/modules/sessions/service.py backend/app/modules/sessions/router.py backend/tests/test_sessions_records_api.py
git commit -m "feat(sessions): add transcript, metrics, and presigned recording-url endpoints"
```

---

### Task 6: Session Reconciliation Job & Cross-Tenant Records Isolation Tests

**Files:**
- Create: `backend/app/modules/sessions/reconciliation.py`
- Create: `backend/tests/test_sessions_records_cross_tenant.py`
- Test: `backend/tests/test_sessions_records_cross_tenant.py`

**Interfaces:**
- Consumes: `SessionRepository`, `create_access_token`.
- Produces:
  - `reconcile_orphaned_sessions(stale_threshold_seconds: int = 600) -> int`: reconciles unfinalized dead sessions.
  - Verification that Tenant B cannot access Tenant A's transcripts, metrics, or audio recordings.

- [ ] **Step 1: Write cross-tenant isolation and reconciliation tests**

Create `backend/tests/test_sessions_records_cross_tenant.py`:
```python
"""Tests for session reconciliation and cross-tenant records access prevention."""

import uuid
import pytest
from httpx import AsyncClient

from backend.app.core.security import create_access_token
from backend.app.core.settings import settings
from backend.app.modules.sessions.reconciliation import reconcile_orphaned_sessions
from backend.app.modules.sessions.repository import SessionRepository


@pytest.mark.asyncio
async def test_reconcile_orphaned_sessions() -> None:
    """Verify reconciliation job closes stale initiated/active sessions as failed/abandoned."""
    repo = SessionRepository()
    org_id = str(uuid.uuid4())
    sess = await repo.create_session(
        organization_id=org_id,
        agent_id=str(uuid.uuid4()),
        agent_version_id=str(uuid.uuid4()),
        channel="web",
        room_name=f"stale-{uuid.uuid4().hex[:6]}",
    )

    # Run reconciliation with 0 threshold to capture session
    closed_count = await reconcile_orphaned_sessions(repository=repo, stale_threshold_seconds=0)
    assert closed_count >= 1

    updated = await repo.get_by_id_internal(sess["id"])
    assert updated is not None
    assert updated["status"] == "failed"
    assert updated["outcome"] == "abandoned"


@pytest.mark.asyncio
async def test_cross_tenant_records_isolation(async_client: AsyncClient) -> None:
    """Verify Org B cannot fetch Org A's transcripts, metrics, or recording URLs."""
    token_a = create_access_token(data={"sub": "usr-a", "organization_id": "org-alpha", "role": "owner"})
    token_b = create_access_token(data={"sub": "usr-b", "organization_id": "org-beta", "role": "owner"})
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    # Org A creates session and records
    agent_res = await async_client.post("/agents", headers=headers_a, json={"name": "A", "system_prompt": "A"})
    agent_id = agent_res.json()["id"]

    sess_res = await async_client.post("/sessions/web", headers=headers_a, json={"agent_id": agent_id})
    session_id = sess_res.json()["session_id"]

    await async_client.post(
        f"/internal/sessions/{session_id}/finalize",
        headers=internal_headers,
        json={
            "duration_s": 20,
            "transcript_segments": [{"seq": 1, "speaker": "caller", "text": "Secret info"}],
            "metrics": {"avg_latency_ms": 200},
        },
    )

    # Org B attempts to read transcript -> 404
    res_b_trans = await async_client.get(f"/sessions/{session_id}/transcript", headers=headers_b)
    assert res_b_trans.status_code == 404

    # Org B attempts to read metrics -> 404
    res_b_metrics = await async_client.get(f"/sessions/{session_id}/metrics", headers=headers_b)
    assert res_b_metrics.status_code == 404

    # Org B attempts to get recording URL -> 404
    res_b_rec = await async_client.get(f"/sessions/{session_id}/recording-url", headers=headers_b)
    assert res_b_rec.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest backend/tests/test_sessions_records_cross_tenant.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.modules.sessions.reconciliation'`

- [ ] **Step 3: Implement `reconciliation.py`**

Create `backend/app/modules/sessions/reconciliation.py`:
```python
"""Background reconciliation for orphaned or unfinalized sessions."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.sessions.models import Session
from backend.app.modules.sessions.repository import SessionRepository


async def reconcile_orphaned_sessions(
    repository: SessionRepository | None = None,
    session: AsyncSession | None = None,
    stale_threshold_seconds: int = 600,
) -> int:
    """Close orphaned sessions with no heartbeat past the stale threshold as failed/abandoned."""
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=stale_threshold_seconds)

    if session is not None:
        result = await session.execute(
            select(Session).where(
                Session.status.in_(["initiated", "active"]),
                Session.started_at <= cutoff,
            )
        )
        stale_records = result.scalars().all()
        for s in stale_records:
            s.status = "failed"
            s.outcome = "abandoned"
            s.ended_at = now
            if s.started_at:
                s.duration_s = int((now - s.started_at).total_seconds())
        await session.flush()
        return len(stale_records)

    repo = repository or SessionRepository()
    closed = 0
    for sess in repo._mock_sessions.values():
        if sess.get("status") in ("initiated", "active"):
            started = sess.get("started_at", now)
            if started <= cutoff:
                sess["status"] = "failed"
                sess["outcome"] = "abandoned"
                sess["ended_at"] = now
                sess["duration_s"] = int((now - started).total_seconds()) if started else 0
                closed += 1
    return closed
```

- [ ] **Step 4: Run all verification commands**

Run:
```bash
./.venv/bin/ruff check . && ./.venv/bin/ruff format --check .
./.venv/bin/mypy backend worker
./.venv/bin/pytest -v
./.venv/bin/lint-imports
```
Expected output:
- All Ruff checks passing.
- Mypy clean.
- All tests passing.
- Import boundaries intact (0 broken).

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/sessions/reconciliation.py backend/tests/test_sessions_records_cross_tenant.py
git commit -m "feat(sessions): implement reconciliation job and verify cross-tenant records isolation"
```
