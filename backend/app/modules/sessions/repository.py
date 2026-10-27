"""Sessions repository."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.sessions.models import Session, SessionMetric, TranscriptSegment


def _canonical_uuid(val: Any) -> str:
    """Normalize a UUID string or UUID object to canonical lowercase hex format."""
    if not val:
        return ""
    try:
        return str(uuid.UUID(str(val)))
    except (ValueError, TypeError, AttributeError):
        return str(val).strip().lower()


def _parse_session_uuid(session_id: str) -> uuid.UUID | None:
    """Safely parse a session ID string to a UUID, stripping sess- prefix."""
    try:
        clean = session_id.removeprefix("sess-")
        return uuid.UUID(clean)
    except (ValueError, TypeError, AttributeError):
        return None


class SessionRepository:
    """Repository handling persistence for voice sessions and transcripts."""

    _mock_sessions: dict[str, dict[str, Any]] = {}
    _mock_transcripts: dict[str, list[dict[str, Any]]] = {}
    _mock_metrics: dict[str, dict[str, Any]] = {}

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

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
            try:
                org_uuid = uuid.UUID(organization_id)
                agent_uuid = uuid.UUID(agent_id)
                version_uuid = uuid.UUID(agent_version_id)
            except ValueError:
                org_uuid = uuid.uuid4()
                agent_uuid = uuid.uuid4()
                version_uuid = uuid.uuid4()

            sess = Session(
                organization_id=org_uuid,
                agent_id=agent_uuid,
                agent_version_id=version_uuid,
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
        canon_org = _canonical_uuid(organization_id)
        canon_sess = _canonical_uuid(session_id)

        if self.session is not None:
            sess_uuid = _parse_session_uuid(session_id)
            try:
                org_uuid = uuid.UUID(organization_id)
            except ValueError:
                return None
            if sess_uuid is None:
                return None
            result = await self.session.execute(
                select(Session).where(Session.id == sess_uuid, Session.organization_id == org_uuid)
            )
            db_sess = result.scalar_one_or_none()
            if not db_sess:
                return None
            return {
                "id": str(db_sess.id),
                "organization_id": str(db_sess.organization_id),
                "agent_id": str(db_sess.agent_id),
                "agent_version_id": str(db_sess.agent_version_id),
                "channel": db_sess.channel,
                "status": db_sess.status,
                "outcome": db_sess.outcome,
                "outcome_label": db_sess.outcome_label,
                "room_name": db_sess.room_name,
                "started_at": db_sess.started_at,
                "ended_at": db_sess.ended_at,
                "duration_s": db_sess.duration_s,
                "recording_key": db_sess.recording_key,
                "created_at": db_sess.created_at,
            }

        mock_sess = self._mock_sessions.get(session_id)
        if not mock_sess:
            for s in self._mock_sessions.values():
                if _canonical_uuid(s["id"]) == canon_sess:
                    mock_sess = s
                    break
        if not mock_sess or _canonical_uuid(mock_sess.get("organization_id")) != canon_org:
            return None
        return mock_sess

    async def get_by_id_internal(self, session_id: str) -> dict[str, Any] | None:
        """Fetch session by ID for worker internal runtime configuration."""
        canon_sess = _canonical_uuid(session_id)
        if self.session is not None:
            sess_uuid = _parse_session_uuid(session_id)
            if sess_uuid is None:
                return None
            result = await self.session.execute(select(Session).where(Session.id == sess_uuid))
            db_sess = result.scalar_one_or_none()
            if not db_sess:
                return None
            return {
                "id": str(db_sess.id),
                "organization_id": str(db_sess.organization_id),
                "agent_id": str(db_sess.agent_id),
                "agent_version_id": str(db_sess.agent_version_id),
                "channel": db_sess.channel,
                "status": db_sess.status,
                "outcome": db_sess.outcome,
                "outcome_label": db_sess.outcome_label,
                "room_name": db_sess.room_name,
                "started_at": db_sess.started_at,
                "ended_at": db_sess.ended_at,
                "duration_s": db_sess.duration_s,
                "recording_key": db_sess.recording_key,
                "created_at": db_sess.created_at,
            }

        mock_sess = self._mock_sessions.get(session_id)
        if not mock_sess:
            for s in self._mock_sessions.values():
                if _canonical_uuid(s["id"]) == canon_sess:
                    return s
        return mock_sess

    async def get_by_room_name(self, room_name: str) -> dict[str, Any] | None:
        """Fetch session by unique LiveKit room name."""
        if self.session is not None:
            result = await self.session.execute(
                select(Session).where(Session.room_name == room_name)
            )
            db_sess = result.scalar_one_or_none()
            if not db_sess:
                return None
            return {
                "id": str(db_sess.id),
                "organization_id": str(db_sess.organization_id),
                "agent_id": str(db_sess.agent_id),
                "agent_version_id": str(db_sess.agent_version_id),
                "channel": db_sess.channel,
                "status": db_sess.status,
                "outcome": db_sess.outcome,
                "outcome_label": db_sess.outcome_label,
                "room_name": db_sess.room_name,
                "started_at": db_sess.started_at,
                "ended_at": db_sess.ended_at,
                "duration_s": db_sess.duration_s,
                "recording_key": db_sess.recording_key,
                "created_at": db_sess.created_at,
            }

        for s in self._mock_sessions.values():
            if s.get("room_name") == room_name:
                return s
        return None

    async def list_by_org(
        self,
        organization_id: str,
        limit: int = 50,
        offset: int = 0,
        agent_id: str | None = None,
        status: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List sessions belonging to an organization with paginated filtering."""
        canon_org = _canonical_uuid(organization_id)
        if self.session is not None:
            try:
                org_uuid = uuid.UUID(organization_id)
            except ValueError:
                return [], 0
            conditions = [Session.organization_id == org_uuid]
            if agent_id:
                agent_uuid = _parse_session_uuid(agent_id)
                if agent_uuid:
                    conditions.append(Session.agent_id == agent_uuid)
            if status:
                conditions.append(Session.status == status)
            if from_time:
                conditions.append(Session.created_at >= from_time)
            if to_time:
                conditions.append(Session.created_at <= to_time)

            count_res = await self.session.execute(
                select(func.count()).select_from(Session).where(*conditions)
            )
            total = count_res.scalar_one() or 0

            result = await self.session.execute(
                select(Session)
                .where(*conditions)
                .order_by(desc(Session.created_at))
                .limit(limit)
                .offset(offset)
            )
            db_items = result.scalars().all()
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
                for s in db_items
            ], total

        mock_items = [
            s
            for s in self._mock_sessions.values()
            if _canonical_uuid(s.get("organization_id")) == canon_org
        ]
        if agent_id:
            mock_items = [
                s
                for s in mock_items
                if _canonical_uuid(s.get("agent_id")) == _canonical_uuid(agent_id)
            ]
        if status:
            mock_items = [s for s in mock_items if s.get("status") == status]
        if from_time:
            mock_items = [
                s
                for s in mock_items
                if (c_at := s.get("created_at")) is not None and c_at >= from_time
            ]
        if to_time:
            mock_items = [
                s
                for s in mock_items
                if (c_at := s.get("created_at")) is not None and c_at <= to_time
            ]

        mock_items.sort(key=lambda s: s.get("created_at") or datetime.min, reverse=True)
        return mock_items[offset : offset + limit], len(mock_items)

    async def update_status(
        self,
        session_id: str,
        status: str,
        outcome: str | None = None,
        outcome_label: str | None = None,
        duration_s: int | None = None,
        recording_key: str | None = None,
    ) -> dict[str, Any] | None:
        """Update session lifecycle status, outcome, duration, and recording key."""
        now = datetime.now(UTC)
        canon_sess = _canonical_uuid(session_id)
        if self.session is not None:
            sess_uuid = _parse_session_uuid(session_id)
            if sess_uuid is None:
                return None
            values: dict[str, Any] = {
                "status": status,
                "updated_at": now,
            }
            if outcome is not None:
                values["outcome"] = outcome
            if outcome_label is not None:
                values["outcome_label"] = outcome_label
            if duration_s is not None:
                values["duration_s"] = duration_s
            if recording_key is not None:
                values["recording_key"] = recording_key
            if status in ("completed", "failed"):
                values["ended_at"] = now

            await self.session.execute(
                update(Session).where(Session.id == sess_uuid).values(**values)
            )
            await self.session.flush()
            return await self.get_by_id_internal(session_id)

        mock_sess = self._mock_sessions.get(session_id)
        if not mock_sess:
            for s in self._mock_sessions.values():
                if _canonical_uuid(s["id"]) == canon_sess:
                    mock_sess = s
                    break
        if not mock_sess:
            return None
        mock_sess["status"] = status
        if outcome is not None:
            mock_sess["outcome"] = outcome
        if outcome_label is not None:
            mock_sess["outcome_label"] = outcome_label
        if duration_s is not None:
            mock_sess["duration_s"] = duration_s
        if recording_key is not None:
            mock_sess["recording_key"] = recording_key
        if status in ("completed", "failed"):
            mock_sess["ended_at"] = now
        return mock_sess

    async def create_transcript_segments(
        self, session_id: str, segments: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Persist ordered transcript segments for a session."""
        now = datetime.now(UTC)
        if self.session is not None:
            sess_uuid = _parse_session_uuid(session_id)
            if sess_uuid is None:
                return []
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
                "seq": int(s["seq"]),
                "speaker": str(s["speaker"]),
                "text": str(s["text"]),
                "started_at_ms": int(s.get("started_at_ms", 0)),
                "created_at": now,
            }
            res.append(rec)
        self._mock_transcripts.setdefault(session_id, []).extend(res)
        return res

    async def get_transcript(self, session_id: str) -> list[dict[str, Any]]:
        """Retrieve ordered transcript segments for a session."""
        if self.session is not None:
            sess_uuid = _parse_session_uuid(session_id)
            if sess_uuid is None:
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

        items = self._mock_transcripts.get(session_id)
        if items is None:
            canon = _canonical_uuid(session_id)
            for k, v in self._mock_transcripts.items():
                if _canonical_uuid(k) == canon:
                    items = v
                    break
        items = items or []
        return sorted(items, key=lambda x: int(x["seq"]))

    async def create_or_update_metrics(
        self, session_id: str, metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """Persist or update turn latency and token metrics for a session."""
        now = datetime.now(UTC)
        if self.session is not None:
            sess_uuid = _parse_session_uuid(session_id)
            if sess_uuid is None:
                return {}
            # Query existing to avoid UniqueConstraint violation on retry
            res = await self.session.execute(
                select(SessionMetric).where(SessionMetric.session_id == sess_uuid)
            )
            existing_metric = res.scalar_one_or_none()
            if existing_metric:
                if "avg_latency_ms" in metrics:
                    existing_metric.avg_latency_ms = metrics.get("avg_latency_ms")
                if "p95_latency_ms" in metrics:
                    existing_metric.p95_latency_ms = metrics.get("p95_latency_ms")
                if "interruption_count" in metrics:
                    existing_metric.interruption_count = int(metrics["interruption_count"])
                if "llm_tokens_used" in metrics:
                    existing_metric.llm_tokens_used = int(metrics["llm_tokens_used"])
                if "stt_seconds_billed" in metrics:
                    existing_metric.stt_seconds_billed = float(metrics["stt_seconds_billed"])
                if "tts_characters_billed" in metrics:
                    existing_metric.tts_characters_billed = int(metrics["tts_characters_billed"])
                metric_item = existing_metric
            else:
                metric_item = SessionMetric(
                    session_id=sess_uuid,
                    avg_latency_ms=metrics.get("avg_latency_ms"),
                    p95_latency_ms=metrics.get("p95_latency_ms"),
                    interruption_count=int(metrics.get("interruption_count", 0)),
                    llm_tokens_used=int(metrics.get("llm_tokens_used", 0)),
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

        existing = self._mock_metrics.get(session_id)
        if not existing:
            canon = _canonical_uuid(session_id)
            for k, v in self._mock_metrics.items():
                if _canonical_uuid(k) == canon:
                    existing = v
                    break

        if existing:
            if "avg_latency_ms" in metrics:
                existing["avg_latency_ms"] = metrics.get("avg_latency_ms")
            if "p95_latency_ms" in metrics:
                existing["p95_latency_ms"] = metrics.get("p95_latency_ms")
            if "interruption_count" in metrics:
                existing["interruption_count"] = int(metrics["interruption_count"])
            if "llm_tokens_used" in metrics:
                existing["llm_tokens_used"] = int(metrics["llm_tokens_used"])
            if "stt_seconds_billed" in metrics:
                existing["stt_seconds_billed"] = float(metrics["stt_seconds_billed"])
            if "tts_characters_billed" in metrics:
                existing["tts_characters_billed"] = int(metrics["tts_characters_billed"])
            return existing

        rec = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "avg_latency_ms": metrics.get("avg_latency_ms"),
            "p95_latency_ms": metrics.get("p95_latency_ms"),
            "interruption_count": int(metrics.get("interruption_count", 0)),
            "llm_tokens_used": int(metrics.get("llm_tokens_used", 0)),
            "stt_seconds_billed": float(metrics.get("stt_seconds_billed", 0.0)),
            "tts_characters_billed": int(metrics.get("tts_characters_billed", 0)),
            "created_at": now,
        }
        self._mock_metrics[session_id] = rec
        return rec

    async def get_metrics(self, session_id: str) -> dict[str, Any] | None:
        """Fetch session metrics by session ID."""
        if self.session is not None:
            sess_uuid = _parse_session_uuid(session_id)
            if sess_uuid is None:
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

        m_res = self._mock_metrics.get(session_id)
        if not m_res:
            canon = _canonical_uuid(session_id)
            for k, v in self._mock_metrics.items():
                if _canonical_uuid(k) == canon:
                    return v
        return m_res

    async def update_recording_key(
        self, session_id: str, recording_key: str
    ) -> dict[str, Any] | None:
        """Update session with object storage recording key."""
        now = datetime.now(UTC)
        if self.session is not None:
            sess_uuid = _parse_session_uuid(session_id)
            if sess_uuid is None:
                return None
            await self.session.execute(
                update(Session)
                .where(Session.id == sess_uuid)
                .values(recording_key=recording_key, updated_at=now)
            )
            await self.session.flush()
            return await self.get_by_id_internal(session_id)

        sess = self._mock_sessions.get(session_id)
        if not sess:
            canon = _canonical_uuid(session_id)
            for s in self._mock_sessions.values():
                if _canonical_uuid(s["id"]) == canon:
                    sess = s
                    break
        if not sess:
            return None
        sess["recording_key"] = recording_key
        sess["updated_at"] = now
        return sess
