"""Billing router."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.modules.billing.schemas import PlanResponse, UsageResponse
from backend.app.modules.billing.service import BillingService

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(
    service: BillingService = Depends(BillingService),
) -> list[PlanResponse]:
    """Retrieve all available subscription plans."""
    return await service.list_plans()


@router.get("/plans/{code}", response_model=PlanResponse)
async def get_plan(
    code: str,
    service: BillingService = Depends(BillingService),
) -> PlanResponse:
    """Retrieve plan details by plan code."""
    plan = await service.get_plan_by_code(code)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )
    return plan


@router.get("/usage/{organization_id}", response_model=UsageResponse)
async def get_usage(
    organization_id: str,
    service: BillingService = Depends(BillingService),
) -> UsageResponse:
    """Retrieve aggregated usage for a specific organization."""
    return await service.get_usage(organization_id)
