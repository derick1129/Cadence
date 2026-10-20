"""Sessions repository."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.sessions.models import Session


def _canonical_uuid(val: Any) -> str:
    """Normalize a UUID string or UUID object to canonical lowercase hex format."""
    if not val:
        return ""
    try:
        return str(uuid.UUID(str(val)))
    except (ValueError, TypeError, AttributeError):
        return str(val).strip().lower()


class SessionRepository:
    """Repository handling persistence for voice sessions and transcripts."""

    _mock_sessions: dict[str, dict[str, Any]] = {}

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
            try:
                org_uuid = uuid.UUID(organization_id)
                sess_uuid = uuid.UUID(session_id.replace("sess-", ""))
            except ValueError:
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
            try:
                sess_uuid = uuid.UUID(session_id.replace("sess-", ""))
            except ValueError:
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

    async def list_by_org(
        self, organization_id: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        """List sessions belonging to an organization with pagination."""
        canon_org = _canonical_uuid(organization_id)
        if self.session is not None:
            try:
                org_uuid = uuid.UUID(organization_id)
            except ValueError:
                return [], 0
            count_res = await self.session.execute(
                select(func.count()).select_from(Session).where(Session.organization_id == org_uuid)
            )
            total = count_res.scalar_one() or 0

            result = await self.session.execute(
                select(Session)
                .where(Session.organization_id == org_uuid)
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
            try:
                sess_uuid = uuid.UUID(session_id.replace("sess-", ""))
            except ValueError:
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
