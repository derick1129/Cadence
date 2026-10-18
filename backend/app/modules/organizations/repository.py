"""Organization repository handling persistence for organizations and memberships."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.organizations.models import Membership, Organization


def _parse_uuid(val: str | uuid.UUID | None) -> uuid.UUID | None:
    """Safely parse a string or UUID into a uuid.UUID object."""
    if val is None:
        return None
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, AttributeError):
        return None


class OrganizationRepository:
    """Repository handling persistence for organizations and memberships."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self._mock_orgs: dict[str, dict[str, Any]] = {}
        self._mock_members: list[dict[str, Any]] = []

    async def get_organization(self, organization_id: str) -> dict[str, Any] | None:
        """Fetch organization record by organization_id."""
        if self.session is not None:
            org_uuid = _parse_uuid(organization_id)
            if org_uuid is None:
                return None
            result = await self.session.execute(
                select(Organization).where(Organization.id == org_uuid)
            )
            org = result.scalar_one_or_none()
            if not org:
                return None
            return {
                "id": str(org.id),
                "name": org.name,
                "plan_id": org.plan_id,
                "stripe_customer_id": org.stripe_customer_id,
                "created_at": org.created_at,
                "updated_at": org.updated_at,
            }
        return self._mock_orgs.get(organization_id)

    async def get_by_id(self, organization_id: str) -> dict[str, Any] | None:
        """Backward-compatible alias for get_organization."""
        return await self.get_organization(organization_id)

    async def create_organization(
        self,
        name: str,
        plan_id: str = "free",
        stripe_customer_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new tenant organization."""
        now = datetime.now(UTC)
        if self.session is not None:
            org = Organization(
                name=name,
                plan_id=plan_id,
                stripe_customer_id=stripe_customer_id,
            )
            self.session.add(org)
            await self.session.flush()
            return {
                "id": str(org.id),
                "name": org.name,
                "plan_id": org.plan_id,
                "stripe_customer_id": org.stripe_customer_id,
                "created_at": org.created_at,
                "updated_at": org.updated_at,
            }
        org_id = str(uuid.uuid4())
        record = {
            "id": org_id,
            "name": name,
            "plan_id": plan_id,
            "stripe_customer_id": stripe_customer_id,
            "created_at": now,
            "updated_at": now,
        }
        self._mock_orgs[org_id] = record
        return record

    async def create(
        self,
        name: str,
        plan_id: str = "free",
        stripe_customer_id: str | None = None,
    ) -> dict[str, Any]:
        """Backward-compatible alias for create_organization."""
        return await self.create_organization(
            name=name,
            plan_id=plan_id,
            stripe_customer_id=stripe_customer_id,
        )

    async def list_members(self, organization_id: str) -> list[dict[str, Any]]:
        """List all members belonging to an organization."""
        if self.session is not None:
            org_uuid = _parse_uuid(organization_id)
            if org_uuid is None:
                return []
            result = await self.session.execute(
                select(Membership)
                .where(Membership.organization_id == org_uuid)
                .order_by(Membership.created_at.asc())
            )
            members = result.scalars().all()
            return [
                {
                    "id": str(m.id),
                    "user_id": str(m.user_id),
                    "organization_id": str(m.organization_id),
                    "email": "",
                    "role": m.role,
                    "created_at": m.created_at,
                    "updated_at": m.updated_at,
                }
                for m in members
            ]
        return [m for m in self._mock_members if m.get("organization_id") == organization_id]

    async def create_membership(
        self,
        user_id: str,
        organization_id: str,
        role: str = "member",
        email: str = "",
    ) -> dict[str, Any]:
        """Create a membership association between a user and an organization."""
        now = datetime.now(UTC)
        if self.session is not None:
            u_uuid = _parse_uuid(user_id)
            o_uuid = _parse_uuid(organization_id)
            if u_uuid is None or o_uuid is None:
                raise ValueError(
                    f"Invalid UUID: user_id={user_id}, organization_id={organization_id}"
                )
            membership = Membership(
                user_id=u_uuid,
                organization_id=o_uuid,
                role=role,
            )
            self.session.add(membership)
            await self.session.flush()
            return {
                "id": str(membership.id),
                "user_id": str(membership.user_id),
                "organization_id": str(membership.organization_id),
                "email": email,
                "role": membership.role,
                "created_at": membership.created_at,
                "updated_at": membership.updated_at,
            }
        member = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "organization_id": organization_id,
            "email": email,
            "role": role,
            "created_at": now,
            "updated_at": now,
        }
        self._mock_members.append(member)
        return member

    async def add_member(
        self,
        organization_id: str,
        user_id: str = "",
        email: str = "",
        role: str = "member",
    ) -> dict[str, Any]:
        """Backward-compatible alias for create_membership."""
        return await self.create_membership(
            user_id=user_id,
            organization_id=organization_id,
            role=role,
            email=email,
        )

    async def get_membership(self, user_id: str, organization_id: str) -> dict[str, Any] | None:
        """Retrieve membership record for a specific user and organization."""
        if self.session is not None:
            u_uuid = _parse_uuid(user_id)
            o_uuid = _parse_uuid(organization_id)
            if u_uuid is None or o_uuid is None:
                return None
            result = await self.session.execute(
                select(Membership).where(
                    Membership.user_id == u_uuid,
                    Membership.organization_id == o_uuid,
                )
            )
            membership_record = result.scalar_one_or_none()
            if not membership_record:
                return None
            return {
                "id": str(membership_record.id),
                "user_id": str(membership_record.user_id),
                "organization_id": str(membership_record.organization_id),
                "role": membership_record.role,
                "created_at": membership_record.created_at,
                "updated_at": membership_record.updated_at,
            }
        for mock_mem in self._mock_members:
            if (
                mock_mem.get("user_id") == user_id
                and mock_mem.get("organization_id") == organization_id
            ):
                return mock_mem
        return None

    async def remove_membership(self, user_id: str, organization_id: str) -> bool:
        """Remove membership for a user in an organization."""
        if self.session is not None:
            u_uuid = _parse_uuid(user_id)
            o_uuid = _parse_uuid(organization_id)
            if u_uuid is None or o_uuid is None:
                return False
            result = await self.session.execute(
                delete(Membership).where(
                    Membership.user_id == u_uuid,
                    Membership.organization_id == o_uuid,
                )
            )
            await self.session.flush()
            rowcount = getattr(result, "rowcount", 0)
            return bool(rowcount and rowcount > 0)

        initial_count = len(self._mock_members)
        self._mock_members = [
            m
            for m in self._mock_members
            if not (m.get("user_id") == user_id and m.get("organization_id") == organization_id)
        ]
        return len(self._mock_members) < initial_count

    async def get_user_organizations(self, user_id: str) -> list[dict[str, Any]]:
        """Fetch all membership records for a user across organizations."""
        if self.session is not None:
            u_uuid = _parse_uuid(user_id)
            if u_uuid is None:
                return []
            result = await self.session.execute(
                select(Membership)
                .where(Membership.user_id == u_uuid)
                .order_by(Membership.created_at.asc())
            )
            memberships = result.scalars().all()
            return [
                {
                    "id": str(m.id),
                    "user_id": str(m.user_id),
                    "organization_id": str(m.organization_id),
                    "role": m.role,
                    "created_at": m.created_at,
                    "updated_at": m.updated_at,
                }
                for m in memberships
            ]
        return [m for m in self._mock_members if m.get("user_id") == user_id]
