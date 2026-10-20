"""Background reconciliation for orphaned or unfinalized sessions."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
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
            started = sess.get("started_at") or now
            if started <= cutoff:
                sess["status"] = "failed"
                sess["outcome"] = "abandoned"
                sess["ended_at"] = now
                sess["duration_s"] = int((now - started).total_seconds()) if started else 0
                closed += 1
    return closed
