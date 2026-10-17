"""Organization service."""

import uuid
from typing import Any

from backend.app.modules.organizations.repository import OrganizationRepository
from backend.app.modules.organizations.schemas import (
    MemberInvite,
    MemberResponse,
    OrgCreate,
    OrgResponse,
)


class OrganizationService:
    """Business logic for organization management and member invites."""

    def __init__(self, repository: OrganizationRepository | None = None) -> None:
        self.repository = repository or OrganizationRepository()

    async def get_organization(self, org_id: str) -> OrgResponse | None:
        """Fetch organization by org_id."""
        record = await self.repository.get_organization(org_id)
        if not record:
            return None
        return OrgResponse(
            id=record["id"],
            name=record["name"],
            plan_id=record.get("plan_id"),
            stripe_customer_id=record.get("stripe_customer_id"),
            created_at=record.get("created_at"),
        )

    async def create_organization(self, data: OrgCreate) -> OrgResponse:
        """Create a new tenant organization."""
        record = await self.repository.create_organization(
            name=data.name,
            plan_id=data.plan_id,
            stripe_customer_id=data.stripe_customer_id,
        )
        return OrgResponse(
            id=record["id"],
            name=record["name"],
            plan_id=record.get("plan_id"),
            stripe_customer_id=record.get("stripe_customer_id"),
            created_at=record.get("created_at"),
        )

    async def list_members(self, org_id: str) -> list[MemberResponse]:
        """List all members scoped to organization_id."""
        records = await self.repository.list_members(org_id)
        return [
            MemberResponse(
                id=item["id"],
                user_id=item["user_id"],
                organization_id=item["organization_id"],
                email=item.get("email", ""),
                role=item["role"],
            )
            for item in records
        ]

    async def add_member(
        self,
        org_id: str,
        data: MemberInvite,
        user_id: str | None = None,
    ) -> MemberResponse:
        """Add or invite a member into organization_id."""
        member_user_id = user_id or str(uuid.uuid4())
        record = await self.repository.create_membership(
            user_id=member_user_id,
            organization_id=org_id,
            email=str(data.email),
            role=data.role,
        )
        return MemberResponse(
            id=record["id"],
            user_id=record["user_id"],
            organization_id=record["organization_id"],
            email=record.get("email", ""),
            role=record["role"],
        )

    async def invite_member(
        self,
        organization_id: str,
        data: MemberInvite,
        user_id: str | None = None,
    ) -> MemberResponse:
        """Backward-compatible alias for add_member."""
        return await self.add_member(
            org_id=organization_id,
            data=data,
            user_id=user_id,
        )

    async def get_membership(self, user_id: str, organization_id: str) -> dict[str, Any] | None:
        """Fetch membership record by user_id and organization_id."""
        return await self.repository.get_membership(
            user_id=user_id, organization_id=organization_id
        )

    async def check_user_membership(self, user_id: str, organization_id: str) -> str | None:
        """Return user's role in organization, or None if not a member."""
        membership = await self.repository.get_membership(user_id, organization_id)
        if not membership:
            return None
        return str(membership["role"])

    async def remove_member(self, user_id: str, organization_id: str) -> bool:
        """Remove membership for a user in an organization."""
        removed = await self.repository.remove_membership(
            user_id=user_id, organization_id=organization_id
        )
        if not removed:
            removed = await self.repository.remove_membership(
                user_id=organization_id, organization_id=user_id
            )
        return removed

    async def get_user_organizations(self, user_id: str) -> list[dict[str, Any]]:
        """Fetch all organization memberships for a user."""
        return await self.repository.get_user_organizations(user_id)
