"""Billing service."""

from backend.app.modules.billing.repository import BillingRepository
from backend.app.modules.billing.schemas import PlanResponse, UsageResponse


class BillingService:
    """Business logic for subscription plans, quotas, and usage metrics."""

    def __init__(self, repository: BillingRepository | None = None) -> None:
        self.repository = repository or BillingRepository()

    async def list_plans(self) -> list[PlanResponse]:
        """List all available plans."""
        plans = await self.repository.list_plans()
        return [
            PlanResponse(
                id=item["id"],
                code=item["code"],
                name=item["name"],
                max_agents=item["max_agents"],
                max_concurrent_calls=item["max_concurrent_calls"],
                max_monthly_minutes=item["max_monthly_minutes"],
            )
            for item in plans
        ]

    async def get_plan_by_code(self, code: str) -> PlanResponse | None:
        """Fetch plan by unique code."""
        plan = await self.repository.get_plan_by_code(code)
        if not plan:
            return None
        return PlanResponse(
            id=plan["id"],
            code=plan["code"],
            name=plan["name"],
            max_agents=plan["max_agents"],
            max_concurrent_calls=plan["max_concurrent_calls"],
            max_monthly_minutes=plan["max_monthly_minutes"],
        )

    async def get_usage(self, organization_id: str) -> UsageResponse:
        """Fetch tenant usage for organization_id."""
        usage = await self.repository.get_usage_for_org(organization_id)
        return UsageResponse(
            organization_id=usage["organization_id"],
            billing_period_start=usage.get("billing_period_start"),
            billing_period_end=usage.get("billing_period_end"),
            total_seconds=usage.get("total_seconds", 0),
            total_minutes=usage.get("total_minutes", 0),
            current_concurrency=usage.get("current_concurrency", 0),
        )
