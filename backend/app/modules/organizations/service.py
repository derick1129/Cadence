"""Organization service."""

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

    async def get_organization(self, organization_id: str) -> OrgResponse | None:
        """Fetch organization by organization_id."""
        record = await self.repository.get_by_id(organization_id)
        if not record:
            return None
        return OrgResponse(
            id=record["id"],
            name=record["name"],
            plan_id=record.get("plan_id"),
            created_at=record.get("created_at"),
        )

    async def create_organization(self, data: OrgCreate) -> OrgResponse:
        """Create a new tenant organization."""
        record = await self.repository.create(name=data.name)
        return OrgResponse(
            id=record["id"],
            name=record["name"],
            plan_id=record.get("plan_id"),
            created_at=record.get("created_at"),
        )

    async def list_members(self, organization_id: str) -> list[MemberResponse]:
        """List all members scoped to organization_id."""
        records = await self.repository.list_members(organization_id)
        return [
            MemberResponse(
                id=item["id"],
                user_id=item["user_id"],
                organization_id=item["organization_id"],
                email=item["email"],
                role=item["role"],
            )
            for item in records
        ]

    async def invite_member(self, organization_id: str, data: MemberInvite) -> MemberResponse:
        """Invite a member into organization_id."""
        record = await self.repository.add_member(
            organization_id=organization_id,
            email=str(data.email),
            role=data.role,
        )
        return MemberResponse(
            id=record["id"],
            user_id=record["user_id"],
            organization_id=record["organization_id"],
            email=record["email"],
            role=record["role"],
        )
