"""Organization router."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.modules.organizations.schemas import (
    MemberInvite,
    MemberResponse,
    OrgCreate,
    OrgResponse,
)
from backend.app.modules.organizations.service import OrganizationService

router = APIRouter(prefix="/organizations", tags=["organizations"])


def get_organization_service() -> OrganizationService:
    """Dependency provider returning an OrganizationService instance."""
    return OrganizationService()


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    request: OrgCreate,
    service: OrganizationService = Depends(get_organization_service),
) -> OrgResponse:
    """Create a new organization."""
    return await service.create_organization(request)


@router.get("/{organization_id}", response_model=OrgResponse)
async def get_organization(
    organization_id: str,
    service: OrganizationService = Depends(get_organization_service),
) -> OrgResponse:
    """Retrieve organization details by ID."""
    org = await service.get_organization(organization_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return org


@router.get("/{organization_id}/members", response_model=list[MemberResponse])
async def list_members(
    organization_id: str,
    service: OrganizationService = Depends(get_organization_service),
) -> list[MemberResponse]:
    """List members belonging to an organization."""
    return await service.list_members(organization_id)


@router.post(
    "/{organization_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    organization_id: str,
    request: MemberInvite,
    service: OrganizationService = Depends(get_organization_service),
) -> MemberResponse:
    """Invite a new member to an organization."""
    return await service.invite_member(organization_id, request)
