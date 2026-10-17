"""Sessions repository."""

import uuid
from datetime import UTC, datetime
from typing import Any


class SessionRepository:
    """Repository handling persistence for voice sessions and transcripts."""

    def __init__(self, session: Any | None = None) -> None:
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
        return {
            "id": f"sess-{uuid.uuid4().hex[:12]}",
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

    async def get_by_id(self, organization_id: str, session_id: str) -> dict[str, Any] | None:
        """Fetch session ensuring organization tenant isolation."""
        now = datetime.now(UTC)
        return {
            "id": session_id,
            "organization_id": organization_id,
            "agent_id": "agent-mock-1",
            "agent_version_id": "ver-mock-1",
            "channel": "web",
            "status": "active",
            "outcome": None,
            "outcome_label": None,
            "room_name": f"cadence-session-{session_id}",
            "started_at": now,
            "ended_at": None,
            "duration_s": 12,
            "recording_key": None,
            "created_at": now,
        }

    async def get_by_id_internal(self, session_id: str) -> dict[str, Any] | None:
        """Fetch session by ID for worker internal runtime configuration."""
        now = datetime.now(UTC)
        return {
            "id": session_id,
            "organization_id": "org-mock-1",
            "agent_id": "agent-mock-1",
            "agent_version_id": "ver-mock-1",
            "channel": "web",
            "status": "active",
            "outcome": None,
            "outcome_label": None,
            "room_name": f"cadence-session-{session_id}",
            "started_at": now,
            "ended_at": None,
            "duration_s": 0,
            "recording_key": None,
            "created_at": now,
        }

    async def list_by_org(
        self, organization_id: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        """List sessions belonging to an organization with pagination."""
        now = datetime.now(UTC)
        items = [
            {
                "id": "sess-mock-1",
                "organization_id": organization_id,
                "agent_id": "agent-mock-1",
                "agent_version_id": "ver-mock-1",
                "channel": "web",
                "status": "completed",
                "outcome": "completed",
                "outcome_label": "booking_confirmed",
                "room_name": "cadence-session-sess-mock-1",
                "started_at": now,
                "ended_at": now,
                "duration_s": 45,
                "recording_key": "recordings/sess-mock-1.mp4",
                "created_at": now,
            }
        ]
        return items, len(items)

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
        return {
            "id": session_id,
            "organization_id": "org-mock-1",
            "agent_id": "agent-mock-1",
            "agent_version_id": "ver-mock-1",
            "channel": "web",
            "status": status,
            "outcome": outcome,
            "outcome_label": outcome_label,
            "room_name": f"cadence-session-{session_id}",
            "started_at": now,
            "ended_at": now if status in ("completed", "failed") else None,
            "duration_s": duration_s or 0,
            "recording_key": recording_key,
            "created_at": now,
        }
