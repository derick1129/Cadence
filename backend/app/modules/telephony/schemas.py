"""Telephony module schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PhoneNumberResponse(BaseModel):
    """Phone number configuration and routing details."""

    id: str
    organization_id: str
    e164: str
    carrier: str
    agent_id: str | None = None
    trunk_ref: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PhoneNumberAssign(BaseModel):
    """Payload to assign or unassign a phone number to an agent."""

    agent_id: str | None = None
