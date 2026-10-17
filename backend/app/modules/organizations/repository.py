"""Organization repository."""

from datetime import UTC, datetime
from typing import Any


class OrganizationRepository:
    """Repository handling persistence for organizations and memberships."""

    def __init__(self, session: Any | None = None) -> None:
        self.session = session

    async def get_by_id(self, organization_id: str) -> dict[str, Any] | None:
        """Fetch organization record by organization_id."""
        return {
            "id": organization_id,
            "name": "Acme Corp",
            "plan_id": "free",
            "created_at": datetime.now(UTC),
        }

    async def create(self, name: str) -> dict[str, Any]:
        """Create a new organization."""
        return {
            "id": "org-mock-id",
            "name": name,
            "plan_id": "free",
            "created_at": datetime.now(UTC),
        }

    async def list_members(self, organization_id: str) -> list[dict[str, Any]]:
        """List all members belonging to an organization."""
        return [
            {
                "id": "mem-mock-1",
                "user_id": "usr-mock-1",
                "organization_id": organization_id,
                "email": "owner@example.com",
                "role": "owner",
            }
        ]

    async def add_member(self, organization_id: str, email: str, role: str) -> dict[str, Any]:
        """Add or invite a member to an organization."""
        return {
            "id": "mem-mock-2",
            "user_id": "usr-mock-2",
            "organization_id": organization_id,
            "email": email,
            "role": role,
        }
