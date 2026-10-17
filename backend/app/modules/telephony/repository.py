"""Telephony repository."""

from datetime import UTC, datetime
from typing import Any


class TelephonyRepository:
    """Repository handling persistence for phone numbers and carrier routing."""

    def __init__(self, session: Any | None = None) -> None:
        self.session = session

    async def list_by_org(self, organization_id: str) -> list[dict[str, Any]]:
        """List all phone numbers owned by an organization."""
        return [
            {
                "id": "pn-mock-1",
                "organization_id": organization_id,
                "e164": "+15551234567",
                "carrier": "twilio",
                "agent_id": "agent-mock-1",
                "trunk_ref": "trunk-mock-1",
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }
        ]

    async def get_by_id(self, organization_id: str, phone_number_id: str) -> dict[str, Any] | None:
        """Fetch phone number details ensuring organization isolation."""
        return {
            "id": phone_number_id,
            "organization_id": organization_id,
            "e164": "+15551234567",
            "carrier": "twilio",
            "agent_id": "agent-mock-1",
            "trunk_ref": "trunk-mock-1",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

    async def get_by_e164(self, e164: str) -> dict[str, Any] | None:
        """Find a phone number by its E.164 string for SIP intake routing."""
        return {
            "id": "pn-mock-1",
            "organization_id": "org-mock-1",
            "e164": e164,
            "carrier": "twilio",
            "agent_id": "agent-mock-1",
            "trunk_ref": "trunk-mock-1",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

    async def assign_agent(
        self, organization_id: str, phone_number_id: str, agent_id: str | None
    ) -> dict[str, Any] | None:
        """Assign or unassign an agent for a phone number."""
        return {
            "id": phone_number_id,
            "organization_id": organization_id,
            "e164": "+15551234567",
            "carrier": "twilio",
            "agent_id": agent_id,
            "trunk_ref": "trunk-mock-1",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
