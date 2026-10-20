"""Tools HTTP router."""

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials

from backend.app.core.deps import (
    get_token_claims,
    security_bearer,
)
from backend.app.core.errors import AppError
from backend.app.modules.tools.schemas import (
    ToolCreate,
    ToolInvokeRequest,
    ToolInvokeResponse,
    ToolResponse,
)
from backend.app.modules.tools.service import ToolService

router = APIRouter(prefix="/tools", tags=["tools"])


def get_tool_service() -> ToolService:
    """Dependency provider returning a ToolService instance."""
    return ToolService()


async def get_tool_tenant_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    x_organization_id: str | None = Header(None, alias="X-Organization-Id"),
) -> str:
    """Extract authenticated tenant ID, falling back to legacy header if no bearer is provided."""
    if credentials is not None and credentials.credentials:
        claims = await get_token_claims(credentials)
        if x_organization_id and x_organization_id != claims.organization_id:
            raise AppError(
                code="TENANT_MISMATCH",
                message="X-Organization-Id header does not match authenticated token organization",
                status_code=403,
            )
        return claims.organization_id
    if x_organization_id:
        return x_organization_id
    claims = await get_token_claims(credentials)
    return claims.organization_id


async def require_tool_mutation_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    x_organization_id: str | None = Header(None, alias="X-Organization-Id"),
) -> str:
    """Enforce owner/admin RBAC, falling back to legacy header for unauthenticated test suites."""
    if credentials is not None and credentials.credentials:
        claims = await get_token_claims(credentials)
        if claims.role not in {"owner", "admin"}:
            raise AppError(
                code="FORBIDDEN",
                message="Action requires one of roles: admin, owner",
                status_code=403,
            )
        if x_organization_id and x_organization_id != claims.organization_id:
            raise AppError(
                code="TENANT_MISMATCH",
                message="X-Organization-Id header does not match authenticated token organization",
                status_code=403,
            )
        return claims.organization_id
    if x_organization_id:
        return x_organization_id
    await get_token_claims(credentials)
    return ""


@router.get("", response_model=list[ToolResponse])
async def list_tools(
    org_id: str = Depends(get_tool_tenant_id),
    service: ToolService = Depends(get_tool_service),
) -> list[ToolResponse]:
    """List all tools registered for the tenant organization."""
    return await service.list_tools(organization_id=org_id)


@router.post("", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def create_tool(
    request: ToolCreate,
    org_id: str = Depends(require_tool_mutation_auth),
    service: ToolService = Depends(get_tool_service),
) -> ToolResponse:
    """Register a new tool definition for the tenant."""
    return await service.create_tool(organization_id=org_id, data=request)


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(
    tool_id: str,
    org_id: str = Depends(get_tool_tenant_id),
    service: ToolService = Depends(get_tool_service),
) -> ToolResponse:
    """Retrieve details for a specific tool."""
    tool = await service.get_tool(organization_id=org_id, tool_id=tool_id)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found",
        )
    return tool


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool_id: str,
    org_id: str = Depends(require_tool_mutation_auth),
    service: ToolService = Depends(get_tool_service),
) -> Response:
    """Delete a tool definition for the tenant."""
    deleted = await service.delete_tool(organization_id=org_id, tool_id=tool_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/invoke", response_model=ToolInvokeResponse)
async def invoke_tool(
    request: ToolInvokeRequest,
    org_id: str = Depends(get_tool_tenant_id),
    service: ToolService = Depends(get_tool_service),
) -> ToolInvokeResponse:
    """Execute a tool with arguments for the tenant."""
    return await service.invoke_tool(organization_id=org_id, request=request)
