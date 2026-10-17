"""Billing and usage schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PlanResponse(BaseModel):
    """Subscription plan details."""

    id: str
    code: str
    name: str
    max_agents: int
    max_concurrent_calls: int
    max_monthly_minutes: int

    model_config = ConfigDict(from_attributes=True)


class UsageResponse(BaseModel):
    """Usage aggregates and limits for an organization."""

    organization_id: str
    billing_period_start: datetime | None = None
    billing_period_end: datetime | None = None
    total_seconds: int = 0
    total_minutes: int = 0
    current_concurrency: int = 0

    model_config = ConfigDict(from_attributes=True)
