"""Tests for Organization repository, service, and HTTP router."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import AppError, app_error_handler
from backend.app.core.security import create_access_token
from backend.app.modules.organizations.models import Membership, Organization
from backend.app.modules.organizations.repository import (
    OrganizationRepository,
    _parse_uuid,
)
from backend.app.modules.organizations.router import (
    get_organization_service,
)
from backend.app.modules.organizations.router import (
    router as org_router,
)
from backend.app.modules.organizations.schemas import MemberInvite, OrgCreate
from backend.app.modules.organizations.service import OrganizationService


@pytest.fixture
def org_app() -> FastAPI:
    """FastAPI test app for organizations module."""
    app = FastAPI(title="Org Test App")
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.include_router(org_router)
    shared_service = OrganizationService()
    app.dependency_overrides[get_organization_service] = lambda: shared_service
    return app


@pytest.mark.asyncio
async def test_parse_uuid_helper() -> None:
    """Verify _parse_uuid handles valid and invalid UUID inputs."""
    valid_uuid_str = str(uuid.uuid4())
    parsed = _parse_uuid(valid_uuid_str)
    assert parsed == uuid.UUID(valid_uuid_str)

    parsed_obj = _parse_uuid(parsed)
    assert parsed_obj == parsed

    assert _parse_uuid(None) is None
    assert _parse_uuid("not-a-uuid") is None
    assert _parse_uuid(12345) is None  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_organization_crud_in_memory_or_mock() -> None:
    """Verify creating org, adding members, and listing memberships in mock mode."""
    repo = OrganizationRepository()
    service = OrganizationService(repository=repo)

    # 1. Create organization
    org = await service.create_organization(
        OrgCreate(name="Acme Inc", plan_id="pro", stripe_customer_id="cus_123")
    )
    assert org.name == "Acme Inc" and org.id is not None
    assert org.plan_id == "pro" and org.stripe_customer_id == "cus_123"

    # 2. Add owner member via repo
    user_id = str(uuid.uuid4())
    member = await repo.add_member(
        organization_id=org.id, user_id=user_id, email="owner@acme.com", role="owner"
    )
    assert member["role"] == "owner" and member["organization_id"] == org.id

    # 3. List members via service
    members = await service.list_members(org.id)
    assert len(members) == 1 and members[0].email == "owner@acme.com"

    # 4. Verify membership query via repo
    membership = await repo.get_membership(user_id=user_id, organization_id=org.id)
    assert membership is not None and membership["role"] == "owner"

    # 5. Check role query via service
    assert await service.check_user_membership(user_id=user_id, organization_id=org.id) == "owner"

    # 6. Get membership via service
    svc_mem = await service.get_membership(user_id=user_id, organization_id=org.id)
    assert svc_mem is not None and svc_mem["role"] == "owner"

    # 7. Get user organizations via service
    user_orgs = await service.get_user_organizations(user_id=user_id)
    assert len(user_orgs) == 1 and user_orgs[0]["organization_id"] == org.id

    # 8. Add member via service
    member2 = await service.add_member(
        org_id=org.id,
        data=MemberInvite(email="staff@acme.com", role="member"),
    )
    assert member2.email == "staff@acme.com" and member2.role == "member"

    # 9. Remove member via service
    removed = await service.remove_member(user_id=user_id, organization_id=org.id)
    assert removed is True
    assert await service.check_user_membership(user_id=user_id, organization_id=org.id) is None

    # Second member removal
    removed_second = await service.remove_member(user_id=member2.user_id, organization_id=org.id)
    assert removed_second is True

    # Removing non-existent membership returns False
    assert await service.remove_member(user_id="missing-user", organization_id=org.id) is False


@pytest.mark.asyncio
async def test_repository_db_mode_invalid_uuids() -> None:
    """Verify repository methods safely return None/empty/False when given invalid UUIDs."""
    mock_session = AsyncMock(spec=AsyncSession)
    repo = OrganizationRepository(session=mock_session)

    # get_organization with invalid UUID
    assert await repo.get_organization("invalid-uuid") is None
    # list_members with invalid UUID
    assert await repo.list_members("invalid-uuid") == []
    # get_membership with invalid UUID
    assert await repo.get_membership("invalid-user", str(uuid.uuid4())) is None
    assert await repo.get_membership(str(uuid.uuid4()), "invalid-org") is None
    # remove_membership with invalid UUID
    assert await repo.remove_membership("invalid-user", str(uuid.uuid4())) is False
    assert await repo.remove_membership(str(uuid.uuid4()), "invalid-org") is False
    # get_user_organizations with invalid UUID
    assert await repo.get_user_organizations("invalid-user") == []
    # create_membership with invalid UUID raises ValueError
    with pytest.raises(ValueError, match="Invalid UUID"):
        await repo.create_membership(user_id="invalid", organization_id=str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_repository_db_mode_queries() -> None:
    """Verify repository async database operations with session."""
    mock_session = AsyncMock(spec=AsyncSession)
    repo = OrganizationRepository(session=mock_session)

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    mem_id = uuid.uuid4()

    # 1. create_organization in db mode
    org_dict = await repo.create_organization(
        name="DB Org",
        plan_id="team",
        stripe_customer_id="cus_db_1",
    )
    assert org_dict["name"] == "DB Org"
    assert org_dict["plan_id"] == "team"
    mock_session.add.assert_called()
    mock_session.flush.assert_called()

    # 2. get_organization in db mode
    fake_org = Organization(
        name="DB Org",
        plan_id="team",
        stripe_customer_id="cus_db_1",
    )
    fake_org.id = org_id
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_org
    mock_session.execute.return_value = mock_result

    fetched_org = await repo.get_organization(str(org_id))
    assert fetched_org is not None
    assert fetched_org["name"] == "DB Org"
    assert fetched_org["id"] == str(org_id)

    # Missing org
    mock_result.scalar_one_or_none.return_value = None
    assert await repo.get_organization(str(uuid.uuid4())) is None

    # 3. create_membership in db mode
    mem_dict = await repo.create_membership(
        user_id=str(user_id),
        organization_id=str(org_id),
        role="admin",
        email="admin@db.com",
    )
    assert mem_dict["role"] == "admin"
    assert mem_dict["email"] == "admin@db.com"

    # 4. get_membership in db mode
    fake_mem = Membership(
        user_id=user_id,
        organization_id=org_id,
        role="admin",
    )
    fake_mem.id = mem_id
    mock_result.scalar_one_or_none.return_value = fake_mem
    fetched_mem = await repo.get_membership(str(user_id), str(org_id))
    assert fetched_mem is not None
    assert fetched_mem["role"] == "admin"
    assert fetched_mem["user_id"] == str(user_id)

    # 5. list_members in db mode
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [fake_mem]
    mock_result.scalars.return_value = mock_scalars
    members = await repo.list_members(str(org_id))
    assert len(members) == 1
    assert members[0]["user_id"] == str(user_id)

    # 6. get_user_organizations in db mode
    user_orgs = await repo.get_user_organizations(str(user_id))
    assert len(user_orgs) == 1
    assert user_orgs[0]["organization_id"] == str(org_id)

    # 7. remove_membership in db mode
    mock_del_result = MagicMock()
    mock_del_result.rowcount = 1
    mock_session.execute.return_value = mock_del_result
    removed = await repo.remove_membership(str(user_id), str(org_id))
    assert removed is True

    # remove_membership with 0 rowcount returns False
    mock_del_result.rowcount = 0
    assert await repo.remove_membership(str(user_id), str(org_id)) is False


@pytest.mark.asyncio
async def test_backward_compatible_aliases() -> None:
    """Verify backward-compatible aliases on repository and service."""
    repo = OrganizationRepository()
    service = OrganizationService(repository=repo)

    # create alias
    org = await repo.create(name="Alias Corp")
    assert org["name"] == "Alias Corp"

    # get_by_id alias
    fetched = await repo.get_by_id(org["id"])
    assert fetched is not None
    assert fetched["id"] == org["id"]

    # add_member alias
    user_id = str(uuid.uuid4())
    mem = await repo.add_member(
        organization_id=org["id"],
        user_id=user_id,
        email="alias@example.com",
        role="owner",
    )
    assert mem["role"] == "owner"

    # service.invite_member alias
    mem2 = await service.invite_member(
        organization_id=org["id"],
        data=MemberInvite(email="invited@example.com", role="member"),
    )
    assert mem2.email == "invited@example.com"
    assert mem2.role == "member"


@pytest.mark.asyncio
async def test_organization_router_endpoints(org_app: FastAPI) -> None:
    """Verify organization HTTP endpoints."""
    async with AsyncClient(transport=ASGITransport(app=org_app), base_url="http://test") as client:
        # Unauthenticated request is rejected
        unauth_res = await client.post("/organizations", json={"name": "No Auth Org"})
        assert unauth_res.status_code == 401

        # Create organization with auth token
        user_id = str(uuid.uuid4())
        initial_token = create_access_token(
            {"sub": user_id, "organization_id": str(uuid.uuid4()), "role": "owner"}
        )
        init_headers = {"Authorization": f"Bearer {initial_token}"}
        res = await client.post("/organizations", json={"name": "HTTP Org"}, headers=init_headers)
        assert res.status_code == 201
        org_id = res.json()["id"]

        token = create_access_token({"sub": user_id, "organization_id": org_id, "role": "owner"})
        headers = {"Authorization": f"Bearer {token}"}

        # Get organization
        res = await client.get(f"/organizations/{org_id}", headers=headers)
        assert res.status_code == 200 and res.json()["id"] == org_id

        # Invite member
        res = await client.post(
            f"/organizations/{org_id}/members",
            headers=headers,
            json={"email": "colleague@example.com", "role": "member"},
        )
        assert res.status_code == 201 and res.json()["email"] == "colleague@example.com"

        # List members
        res = await client.get(f"/organizations/{org_id}/members", headers=headers)
        assert res.status_code == 200
        assert any(m["email"] == "colleague@example.com" for m in res.json())
        assert any(m["role"] == "owner" and m["user_id"] == user_id for m in res.json())

        # Get non-existent organization with token matching that id (should 404, not 403)
        bad_id = "non-existent-id"
        bad_tok = create_access_token({"sub": "usr", "organization_id": bad_id, "role": "owner"})
        res = await client.get(
            f"/organizations/{bad_id}",
            headers={"Authorization": f"Bearer {bad_tok}"},
        )
        assert res.status_code == 404
