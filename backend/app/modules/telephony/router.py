"""Telephony router."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.modules.telephony.schemas import (
    PhoneNumberAssign,
    PhoneNumberResponse,
)
from backend.app.modules.telephony.service import TelephonyService

router = APIRouter(prefix="/telephony", tags=["telephony"])


def get_telephony_service() -> TelephonyService:
    """Dependency provider for TelephonyService."""
    return TelephonyService()


@router.get("/numbers", response_model=list[PhoneNumberResponse])
async def list_phone_numbers(
    organization_id: str = "org-mock-1",
    service: TelephonyService = Depends(get_telephony_service),
) -> list[PhoneNumberResponse]:
    """List all phone numbers configured for the organization."""
    return await service.list_phone_numbers(organization_id)


@router.get("/numbers/{phone_number_id}", response_model=PhoneNumberResponse)
async def get_phone_number(
    phone_number_id: str,
    organization_id: str = "org-mock-1",
    service: TelephonyService = Depends(get_telephony_service),
) -> PhoneNumberResponse:
    """Retrieve details for a specific phone number."""
    number = await service.get_phone_number(organization_id, phone_number_id)
    if not number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found",
        )
    return number


@router.post(
    "/numbers/{phone_number_id}/assign",
    response_model=PhoneNumberResponse,
)
async def assign_agent(
    phone_number_id: str,
    request: PhoneNumberAssign,
    organization_id: str = "org-mock-1",
    service: TelephonyService = Depends(get_telephony_service),
) -> PhoneNumberResponse:
    """Assign or reassign an agent to a phone number."""
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
