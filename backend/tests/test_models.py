"""Tests for Organization, User, Membership, and RefreshToken ORM models."""

import uuid
from datetime import UTC, datetime, timedelta

from backend.app.modules.auth.models import RefreshToken, User
from backend.app.modules.organizations.models import Membership, Organization


def test_organization_model_creation() -> None:
    """Verify Organization model fields and defaults."""
    org = Organization(name="Acme Corp", plan_id="free")
    assert org.name == "Acme Corp"
    assert org.plan_id == "free"
    assert org.stripe_customer_id is None
    assert isinstance(org.id, uuid.UUID)


def test_user_and_membership_models() -> None:
    """Verify User and Membership model fields and relationship foreign keys."""
    user = User(email="test@example.com", password_hash="hash123", is_active=True)
    assert user.email == "test@example.com"
    assert user.is_active is True

    org_id = uuid.uuid4()
    membership = Membership(
        user_id=user.id,
        organization_id=org_id,
        role="owner",
    )
    assert membership.user_id == user.id
    assert membership.organization_id == org_id
    assert membership.role == "owner"


def test_refresh_token_model() -> None:
    """Verify RefreshToken model fields, expiration, and revocation status."""
    user_id = uuid.uuid4()
    now = datetime.now(UTC)
    expires = now + timedelta(days=7)

    token = RefreshToken(
        user_id=user_id,
        token_hash="sha256-hashed-token-value",
        expires_at=expires,
    )
    assert token.user_id == user_id
    assert token.token_hash == "sha256-hashed-token-value"
    assert token.revoked_at is None
    assert token.is_active(now) is True

    token.revoked_at = now
    assert token.is_active(now) is False
