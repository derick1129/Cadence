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
