"""Organizations router."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.db import get_db
from backend.app.core.deps import (
    TokenClaims,
    get_current_tenant_id,
    get_token_claims,
    require_roles,
)
from backend.app.core.errors import AppError
from backend.app.modules.organizations.schemas import (
    MemberInvite,
    MemberResponse,
    OrgCreate,
    OrgResponse,
)
from backend.app.modules.organizations.service import OrganizationService

router = APIRouter(prefix="/organizations", tags=["organizations"])


def get_organization_service(
    session: AsyncSession = Depends(get_db),
) -> OrganizationService:
    """Dependency provider returning an OrganizationService instance."""
    return OrganizationService(session=session)


# --- Current Tenant Context Endpoints (/me, /members, /current/members) ---


@router.get("/me", response_model=OrgResponse)
async def get_current_organization(
    org_id: str = Depends(get_current_tenant_id),
    service: OrganizationService = Depends(get_organization_service),
) -> OrgResponse:
    """Retrieve details for the authenticated user's current organization."""
    org = await service.get_organization(org_id)
    if not org:
        raise AppError(
            code="ORGANIZATION_NOT_FOUND",
            message="Organization not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return org


@router.get("/members", response_model=list[MemberResponse])
@router.get("/current/members", response_model=list[MemberResponse])
async def list_current_org_members(
    org_id: str = Depends(get_current_tenant_id),
    service: OrganizationService = Depends(get_organization_service),
) -> list[MemberResponse]:
    """List members belonging to the authenticated user's active organization."""
    return await service.list_members(org_id)


@router.post("/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member_to_current_org(
    data: MemberInvite,
    claims: TokenClaims = Depends(require_roles({"owner", "admin"})),
    org_id: str = Depends(get_current_tenant_id),
    service: OrganizationService = Depends(get_organization_service),
) -> MemberResponse:
    """Invite or add a member into the active organization (owner or admin only)."""
    return await service.invite_member(org_id, data)


@router.delete("/members/{user_id}", status_code=status.HTTP_200_OK)
async def remove_member_from_current_org(
    user_id: str,
    claims: TokenClaims = Depends(require_roles({"owner", "admin"})),
    org_id: str = Depends(get_current_tenant_id),
    service: OrganizationService = Depends(get_organization_service),
) -> dict[str, str]:
    """Remove a member from the active organization (owner or admin only)."""
    success = await service.remove_member(user_id=user_id, organization_id=org_id)
    if not success:
        raise AppError(
            code="MEMBER_NOT_FOUND",
            message="Member not found in organization",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return {"status": "ok", "message": "Member removed from organization"}


# --- Explicit Organization ID Endpoints (with cross-tenant validation) ---


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    data: OrgCreate,
    claims: TokenClaims = Depends(get_token_claims),
    service: OrganizationService = Depends(get_organization_service),
) -> OrgResponse:
    """Create a new organization."""
    org = await service.create_organization(data)
    await service.add_member(
        org_id=org.id,
        data=MemberInvite(email="", role="owner"),
        user_id=claims.user_id,
    )
    return org


@router.get("/{organization_id}", response_model=OrgResponse)
async def get_organization(
    organization_id: str,
    claims: TokenClaims = Depends(get_token_claims),
    service: OrganizationService = Depends(get_organization_service),
) -> OrgResponse:
    """Retrieve details for the specified organization ensuring tenant isolation."""
    if claims.organization_id != organization_id:
        raise AppError(
            code="FORBIDDEN",
            message="Access to organization denied",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    org = await service.get_organization(organization_id)
    if not org:
        raise AppError(
            code="ORGANIZATION_NOT_FOUND",
            message="Organization not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return org


@router.get("/{organization_id}/members", response_model=list[MemberResponse])
async def list_members(
    organization_id: str,
    claims: TokenClaims = Depends(get_token_claims),
    service: OrganizationService = Depends(get_organization_service),
) -> list[MemberResponse]:
    """List all members belonging to an organization after verifying tenant context."""
    if claims.organization_id != organization_id:
        raise AppError(
            code="FORBIDDEN",
            message="Access to organization members denied",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return await service.list_members(organization_id)


@router.post(
    "/{organization_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    organization_id: str,
    data: MemberInvite,
    claims: TokenClaims = Depends(require_roles({"owner", "admin"})),
    service: OrganizationService = Depends(get_organization_service),
) -> MemberResponse:
    """Invite or add a member into an organization (owner or admin only)."""
    if claims.organization_id != organization_id:
        raise AppError(
            code="FORBIDDEN",
            message="Cannot invite members to other organizations",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return await service.invite_member(organization_id, data)


@router.delete("/{organization_id}/members/{user_id}", status_code=status.HTTP_200_OK)
async def remove_member(
    organization_id: str,
    user_id: str,
    claims: TokenClaims = Depends(require_roles({"owner", "admin"})),
    service: OrganizationService = Depends(get_organization_service),
) -> dict[str, str]:
    """Remove a member from the specified organization (owner or admin only)."""
    if claims.organization_id != organization_id:
        raise AppError(
            code="FORBIDDEN",
            message="Cannot remove members from other organizations",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    success = await service.remove_member(user_id=user_id, organization_id=organization_id)
    if not success:
        raise AppError(
            code="MEMBER_NOT_FOUND",
            message="Member not found in organization",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return {"status": "ok", "message": "Member removed from organization"}
