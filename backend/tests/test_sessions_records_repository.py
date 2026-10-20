"""Tests for SessionRepository transcript, metrics, and recording persistence."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.sessions.models import TranscriptSegment
from backend.app.modules.sessions.repository import SessionRepository


@pytest.mark.asyncio
async def test_session_repository_records_lifecycle() -> None:
    """Verify persisting and querying transcript segments, metrics,
    and recording keys in mock mode.
    """
    repo = SessionRepository()
    org_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    room = f"test-room-{uuid.uuid4().hex[:6]}"

    # 1. Create Session
    sess = await repo.create_session(
        organization_id=org_id,
        agent_id=agent_id,
        agent_version_id=version_id,
        channel="web",
        room_name=room,
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

    # 5. Fetch by room name
    by_room = await repo.get_by_room_name(room)
    assert by_room is not None
    assert by_room["id"] == session_id

    # 6. Filter list by status
    items, total = await repo.list_by_org(organization_id=org_id, status="initiated")
    assert total >= 1
    assert items[0]["id"] == session_id


@pytest.mark.asyncio
async def test_session_repository_db_session_mode() -> None:
    """Verify repository methods interact with AsyncSession properly."""
    mock_session = AsyncMock(spec=AsyncSession)
    repo = SessionRepository(session=mock_session)

    session_id = str(uuid.uuid4())
    sess_uuid = uuid.UUID(session_id)

    # 1. Transcript segments
    segments = [{"seq": 1, "speaker": "caller", "text": "Hi", "started_at_ms": 100}]
    saved = await repo.create_transcript_segments(session_id, segments)
    assert len(saved) == 1
    assert mock_session.add.called
    assert mock_session.flush.called

    # 2. Get transcript
    fake_segment = TranscriptSegment(
        session_id=sess_uuid,
        seq=1,
        speaker="caller",
        text="Hi",
        started_at_ms=100,
    )
    fake_segment.id = uuid.uuid4()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [fake_segment]
    mock_session.execute.return_value = mock_result

    transcript = await repo.get_transcript(session_id)
    assert len(transcript) == 1
    assert transcript[0]["text"] == "Hi"

    # 3. Create or update metrics
    mock_metric_result = MagicMock()
    mock_metric_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_metric_result

    metrics_res = await repo.create_or_update_metrics(session_id, {"avg_latency_ms": 300})
    assert metrics_res["avg_latency_ms"] == 300
    assert mock_session.add.called
