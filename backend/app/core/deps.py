"""Authentication, tenant context, and authorization dependencies."""

from collections.abc import Awaitable, Callable

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from backend.app.core.errors import AppError
from backend.app.core.security import TokenExpiredError, TokenInvalidError, decode_access_token

security_bearer = HTTPBearer(auto_error=False)


class TokenClaims(BaseModel):
    """Verified claims extracted from an authenticated JWT access token."""

    user_id: str
    organization_id: str
    role: str


async def get_token_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
) -> TokenClaims:
    """Extract and validate bearer JWT token claims."""
    if credentials is None or not credentials.credentials:
        raise AppError(
            code="UNAUTHORIZED",
            message="Missing or invalid Authorization header",
            status_code=401,
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except TokenExpiredError as exc:
        raise AppError(
            code="TOKEN_EXPIRED",
            message="Access token has expired",
            status_code=401,
        ) from exc
    except TokenInvalidError as exc:
        raise AppError(
            code="TOKEN_INVALID",
            message="Invalid access token signature or payload",
            status_code=401,
        ) from exc

    raw_user_id = payload.get("sub")
    raw_org_id = payload.get("organization_id") or payload.get("org")
    raw_role = payload.get("role")

    user_id = str(raw_user_id) if raw_user_id is not None else ""
    org_id = str(raw_org_id) if raw_org_id is not None else ""
    role = str(raw_role) if raw_role is not None else "member"

    if not user_id or not org_id:
        raise AppError(
            code="TOKEN_INVALID",
            message="Token payload is missing required tenant claims",
            status_code=401,
        )

    return TokenClaims(user_id=user_id, organization_id=org_id, role=role)


async def get_current_user_id(
    claims: TokenClaims = Depends(get_token_claims),
) -> str:
    """Extract and return the authenticated user ID."""
    return claims.user_id


async def get_current_tenant_id(
    claims: TokenClaims = Depends(get_token_claims),
    x_organization_id: str | None = Header(None, alias="X-Organization-Id"),
) -> str:
    """Validate and return the active tenant organization ID."""
    if x_organization_id and x_organization_id != claims.organization_id:
        raise AppError(
            code="TENANT_MISMATCH",
            message="X-Organization-Id header does not match authenticated token organization",
            status_code=403,
        )
    return claims.organization_id


def require_roles(
    allowed_roles: set[str] | list[str] | tuple[str, ...],
) -> Callable[..., Awaitable[TokenClaims]]:
    """Dependency factory checking user role matches permitted set."""
    roles_set = set(allowed_roles)

    async def _role_checker(claims: TokenClaims = Depends(get_token_claims)) -> TokenClaims:
        if claims.role not in roles_set:
            raise AppError(
                code="FORBIDDEN",
                message=f"Action requires one of roles: {', '.join(sorted(roles_set))}",
                status_code=403,
            )
        return claims

    return _role_checker


require_role = require_roles
get_current_user = get_token_claims
TokenData = TokenClaims
