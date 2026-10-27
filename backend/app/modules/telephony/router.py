"""Telephony router providing authenticated customer endpoints and legacy compatibility."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.db import get_db
from backend.app.core.deps import (
    TokenClaims,
    get_token_claims,
    require_roles,
)
from backend.app.modules.telephony.repository import TelephonyRepository
from backend.app.modules.telephony.schemas import (
    PhoneNumberAssign,
    PhoneNumberCreate,
    PhoneNumberResponse,
    PhoneNumberUpdate,
)
from backend.app.modules.telephony.service import TelephonyService

router = APIRouter(tags=["telephony"])
phone_numbers_router = APIRouter(prefix="/phone-numbers", tags=["telephony"])
legacy_router = APIRouter(prefix="/telephony", tags=["telephony"])


def get_telephony_service(
    session: AsyncSession = Depends(get_db),
) -> TelephonyService:
    """Dependency provider injecting database session into TelephonyService."""
    repo = TelephonyRepository(session)
    return TelephonyService(repo)


# --- Customer Authenticated Phone Numbers API ---


@phone_numbers_router.post(
    "",
    response_model=PhoneNumberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_phone_number(
    payload: PhoneNumberCreate,
    current_user: TokenClaims = Depends(require_roles({"owner", "admin"})),
    service: TelephonyService = Depends(get_telephony_service),
) -> PhoneNumberResponse:
    """Register or provision a new phone number for the organization."""
    try:
        return await service.create_phone_number(current_user.organization_id, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@phone_numbers_router.get("", response_model=list[PhoneNumberResponse])
async def list_phone_numbers(
    current_user: TokenClaims = Depends(get_token_claims),
    service: TelephonyService = Depends(get_telephony_service),
) -> list[PhoneNumberResponse]:
    """List all phone numbers owned by the current organization."""
    return await service.list_phone_numbers(current_user.organization_id)


@phone_numbers_router.get("/{phone_number_id}", response_model=PhoneNumberResponse)
async def get_phone_number(
    phone_number_id: str,
    current_user: TokenClaims = Depends(get_token_claims),
    service: TelephonyService = Depends(get_telephony_service),
) -> PhoneNumberResponse:
    """Retrieve details for a specific phone number."""
    number = await service.get_phone_number(current_user.organization_id, phone_number_id)
    if not number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found",
        )
    return number


@phone_numbers_router.patch("/{phone_number_id}", response_model=PhoneNumberResponse)
async def update_phone_number(
    phone_number_id: str,
    payload: PhoneNumberUpdate,
    current_user: TokenClaims = Depends(require_roles({"owner", "admin"})),
    service: TelephonyService = Depends(get_telephony_service),
) -> PhoneNumberResponse:
    """Assign or reassign an agent to a phone number."""
    number = await service.assign_agent(
        organization_id=current_user.organization_id,
        phone_number_id=phone_number_id,
        agent_id=payload.agent_id,
    )
    if not number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found",
        )
    return number


@phone_numbers_router.delete("/{phone_number_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_phone_number(
    phone_number_id: str,
    current_user: TokenClaims = Depends(require_roles({"owner", "admin"})),
    service: TelephonyService = Depends(get_telephony_service),
) -> None:
    """Release a phone number from the organization."""
    deleted = await service.delete_phone_number(current_user.organization_id, phone_number_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found",
        )


# --- Legacy Routes for Backward Compatibility ---


@legacy_router.get("/numbers", response_model=list[PhoneNumberResponse])
async def legacy_list_phone_numbers(
    organization_id: str = "org-mock-1",
    service: TelephonyService = Depends(get_telephony_service),
) -> list[PhoneNumberResponse]:
    """Legacy listing endpoint for test harness compatibility."""
    return await service.list_phone_numbers(organization_id)


@legacy_router.get("/numbers/{phone_number_id}", response_model=PhoneNumberResponse)
async def legacy_get_phone_number(
    phone_number_id: str,
    organization_id: str = "org-mock-1",
    service: TelephonyService = Depends(get_telephony_service),
) -> PhoneNumberResponse:
    """Legacy detail endpoint for test harness compatibility."""
    number = await service.get_phone_number(organization_id, phone_number_id)
    if not number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found",
        )
    return number


@legacy_router.post(
    "/numbers/{phone_number_id}/assign",
    response_model=PhoneNumberResponse,
)
async def legacy_assign_agent(
    phone_number_id: str,
    request: PhoneNumberAssign,
    organization_id: str = "org-mock-1",
    service: TelephonyService = Depends(get_telephony_service),
) -> PhoneNumberResponse:
    """Legacy assignment endpoint for test harness compatibility."""
    number = await service.assign_agent(
        organization_id=organization_id,
        phone_number_id=phone_number_id,
        data=request,
    )
    if not number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found",
        )
    return number


# Mount both sub-routers onto the module's main router
router.include_router(phone_numbers_router, prefix="/v1")
router.include_router(legacy_router)
