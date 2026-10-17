"""Organization and membership schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr

OrgRole = Literal["owner", "admin", "member"]


class OrgCreate(BaseModel):
    """Payload to create an organization."""

    name: str


class OrgResponse(BaseModel):
    """Organization details response."""

    id: str
    name: str
    plan_id: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class MemberInvite(BaseModel):
    """Payload to invite a new member to an organization."""

    email: EmailStr
    role: OrgRole = "member"


class MemberResponse(BaseModel):
    """Membership record response."""

    id: str
    user_id: str
    organization_id: str
    email: EmailStr
    role: OrgRole

    model_config = ConfigDict(from_attributes=True)
