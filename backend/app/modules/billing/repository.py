"""Billing repository."""

from datetime import UTC, datetime
from typing import Any


class BillingRepository:
    """Repository handling persistence for subscription plans and usage tracking."""

    def __init__(self, session: Any | None = None) -> None:
        self.session = session

    async def list_plans(self) -> list[dict[str, Any]]:
        """List all available subscription plans."""
        return [
            {
                "id": "plan-free",
                "code": "free",
                "name": "Free",
                "max_agents": 1,
                "max_concurrent_calls": 1,
                "max_monthly_minutes": 30,
            },
            {
                "id": "plan-pro",
                "code": "pro",
                "name": "Pro",
                "max_agents": 10,
                "max_concurrent_calls": 5,
                "max_monthly_minutes": 1000,
            },
        ]

    async def get_plan_by_code(self, code: str) -> dict[str, Any] | None:
        """Fetch plan details by code."""
        for plan in await self.list_plans():
            if plan["code"] == code:
                return plan
        return None

    async def get_usage_for_org(self, organization_id: str) -> dict[str, Any]:
        """Fetch aggregated usage for an organization."""
        now = datetime.now(UTC)
        return {
            "organization_id": organization_id,
            "billing_period_start": now,
            "billing_period_end": now,
            "total_seconds": 0,
            "total_minutes": 0,
            "current_concurrency": 0,
        }
