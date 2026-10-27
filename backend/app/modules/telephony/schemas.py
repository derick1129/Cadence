"""Telephony module schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PhoneNumberCreate(BaseModel):
    """Payload to register or provision a phone number."""

    e164: str = Field(..., description="E.164 formatted telephone number")
    carrier: str = Field("twilio", description="Carrier name (e.g. twilio, telnyx)")
    agent_id: uuid.UUID | str | None = None
    trunk_ref: str | None = None


class PhoneNumberUpdate(BaseModel):
    """Payload to update routing or trunk configuration."""

    agent_id: uuid.UUID | str | None = None
    trunk_ref: str | None = None


class PhoneNumberAssign(BaseModel):
    """Payload to assign or unassign a phone number to an agent."""

    agent_id: uuid.UUID | str | None = None


class PhoneNumberResponse(BaseModel):
    """Phone number configuration and routing details."""

    id: uuid.UUID | str
    organization_id: uuid.UUID | str
    e164: str
    carrier: str
    agent_id: uuid.UUID | str | None = None
    trunk_ref: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
