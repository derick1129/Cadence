"""Authentication service."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import AppError
from backend.app.core.security import (
    create_access_token,
    generate_secure_token,
    hash_password,
    hash_token,
    verify_password,
)
from backend.app.modules.auth.repository import AuthRepository
from backend.app.modules.auth.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from backend.app.modules.organizations import (
    MemberInvite,
    OrganizationService,
    OrgCreate,
)

REFRESH_TOKEN_EXPIRE_DAYS: int = 14


class AuthService:
    """Business logic for authentication, tokens, and registration."""

    def __init__(
        self,
        repository: AuthRepository | None = None,
        org_service: OrganizationService | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        if repository is not None:
            self.repository = repository
        else:
            self.repository = AuthRepository(session=session)

        if org_service is not None:
            self.org_service = org_service
        else:
            self.org_service = OrganizationService(session=session)

    async def signup(self, data: SignupRequest) -> TokenResponse:
        """Register a new user, create initial organization, and issue credentials."""
        normalized_email = data.email.strip().lower()
        existing = await self.repository.get_user_by_email(normalized_email)
        if existing:
            raise AppError(
                code="USER_ALREADY_EXISTS",
                message=f"A user with email '{data.email}' already exists",
                status_code=409,
            )

        hashed_pw = hash_password(data.password)
        user = await self.repository.create_user(
            email=normalized_email,
            password_hash=hashed_pw,
        )

        org_name = data.organization_name or f"{normalized_email.split('@')[0]}'s Org"
        org = await self.org_service.create_organization(OrgCreate(name=org_name))
        await self.org_service.add_member(
            org_id=org.id,
            data=MemberInvite(email=user["email"], role="owner"),
            user_id=user["id"],
        )

        return await self._issue_token_pair(
            user_id=user["id"],
            organization_id=org.id,
            role="owner",
        )

    async def login(self, data: LoginRequest) -> TokenResponse:
        """Authenticate user credentials and issue tenant-scoped tokens."""
        normalized_email = data.email.strip().lower()
        user = await self.repository.get_user_by_email(normalized_email)
        if not user or not verify_password(data.password, user["password_hash"]):
            raise AppError(
                code="INVALID_CREDENTIALS",
                message="Invalid email or password",
                status_code=401,
            )

        if not user.get("is_active", True):
            raise AppError(
                code="USER_INACTIVE",
                message="User account is deactivated",
                status_code=403,
            )

        user_orgs = await self.org_service.get_user_organizations(user["id"])
        if not user_orgs:
            raise AppError(
                code="NO_TENANT_MEMBERSHIP",
                message="User has no tenant memberships",
                status_code=403,
            )

        org_id = user_orgs[0]["organization_id"]
        role = user_orgs[0].get("role", "owner")

        return await self._issue_token_pair(
            user_id=user["id"],
            organization_id=org_id,
            role=role,
        )

    async def refresh_token(self, data: RefreshTokenRequest) -> TokenResponse:
        """Validate refresh token, rotate it, and issue new access credentials."""
        token_digest = hash_token(data.refresh_token)
        stored = await self.repository.get_refresh_token(token_digest)
        if not stored:
            raise AppError(
                code="INVALID_REFRESH_TOKEN",
                message="Refresh token is invalid",
                status_code=401,
            )

        now = datetime.now(UTC)
        expires_at = stored["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if stored.get("revoked_at") is not None or expires_at <= now:
            raise AppError(
                code="INVALID_REFRESH_TOKEN",
                message="Refresh token has expired or been revoked",
                status_code=401,
            )

        user = await self.repository.get_user_by_id(stored["user_id"])
        if not user or not user.get("is_active", True):
            raise AppError(
                code="USER_INACTIVE",
                message="User account is deactivated",
                status_code=403,
            )

        # Atomic single-use revocation of previous token
        await self.repository.revoke_refresh_token(token_digest)

        user_id = stored["user_id"]
        user_orgs = await self.org_service.get_user_organizations(user_id)
        if not user_orgs:
            raise AppError(
                code="NO_TENANT_MEMBERSHIP",
                message="User has no tenant memberships",
                status_code=403,
            )

        org_id = user_orgs[0]["organization_id"]
        role = user_orgs[0].get("role", "owner")

        return await self._issue_token_pair(
            user_id=user_id,
            organization_id=org_id,
            role=role,
        )

    async def get_user_by_id(self, user_id: str) -> UserResponse | None:
        """Retrieve user details by ID."""
        user = await self.repository.get_user_by_id(user_id)
        if not user:
            return None
        return UserResponse(
            id=user["id"],
            email=user["email"],
            is_active=user.get("is_active", True),
        )

    async def _issue_token_pair(
        self, user_id: str, organization_id: str, role: str
    ) -> TokenResponse:
        """Generate access JWT and store hashed opaque refresh token."""
        claims = {
            "sub": user_id,
            "organization_id": organization_id,
            "role": role,
        }
        access_token = create_access_token(data=claims)

        raw_refresh = generate_secure_token(32)
        token_digest = hash_token(raw_refresh)
        expires_at = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        await self.repository.store_refresh_token(
            user_id=user_id,
            token_hash=token_digest,
            expires_at=expires_at,
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=900,
            refresh_token=raw_refresh,
        )
