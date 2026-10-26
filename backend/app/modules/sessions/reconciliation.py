"""Background reconciliation for orphaned or unfinalized sessions."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
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
                func.coalesce(Session.started_at, Session.created_at) <= cutoff,
            )
        )
        stale_records = result.scalars().all()
        for s in stale_records:
            s.status = "failed"
            s.outcome = "abandoned"
            s.ended_at = now
            start_ref: datetime | None = s.started_at or s.created_at
            if start_ref:
                s.duration_s = int((now - start_ref).total_seconds())
        await session.flush()
        return len(stale_records)

    repo = repository or SessionRepository()
    closed = 0
    for sess in repo._mock_sessions.values():
        if sess.get("status") in ("initiated", "active"):
            ref_time = sess.get("started_at") or sess.get("created_at") or now
            if ref_time <= cutoff:
                sess["status"] = "failed"
                sess["outcome"] = "abandoned"
                sess["ended_at"] = now
                start_ref = sess.get("started_at") or sess.get("created_at")
                sess["duration_s"] = int((now - start_ref).total_seconds()) if start_ref else 0
                closed += 1
    return closed
