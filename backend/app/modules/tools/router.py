"""Tools HTTP router."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.db import get_db
from backend.app.core.deps import (
    TokenClaims,
    get_current_tenant_id,
    require_roles,
)
from backend.app.modules.tools.repository import ToolRepository
from backend.app.modules.tools.schemas import (
    ToolCreate,
    ToolInvokeRequest,
    ToolInvokeResponse,
    ToolResponse,
    ToolUpdate,
)
from backend.app.modules.tools.service import ToolService

router = APIRouter(prefix="/tools", tags=["tools"])


def get_tool_service(db: AsyncSession = Depends(get_db)) -> ToolService:
    """Dependency provider returning a ToolService instance wired to the current DB session."""
    return ToolService(repository=ToolRepository(session=db))


@router.get("", response_model=list[ToolResponse])
async def list_tools(
    org_id: str = Depends(get_current_tenant_id),
    service: ToolService = Depends(get_tool_service),
) -> list[ToolResponse]:
    """List all tools registered for the tenant organization."""
    return await service.list_tools(organization_id=org_id)


@router.post("", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def create_tool(
    request: ToolCreate,
    claims: TokenClaims = Depends(require_roles({"owner", "admin"})),
    org_id: str = Depends(get_current_tenant_id),
    service: ToolService = Depends(get_tool_service),
) -> ToolResponse:
    """Register a new tool definition for the tenant."""
    return await service.create_tool(organization_id=org_id, data=request)


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(
    tool_id: str,
    org_id: str = Depends(get_current_tenant_id),
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


@router.patch("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: str,
    request: ToolUpdate,
    claims: TokenClaims = Depends(require_roles({"owner", "admin"})),
    org_id: str = Depends(get_current_tenant_id),
    service: ToolService = Depends(get_tool_service),
) -> ToolResponse:
    """Partially update an existing tool definition (owner and admin only)."""
    tool = await service.update_tool(organization_id=org_id, tool_id=tool_id, data=request)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found",
        )
    return tool


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool_id: str,
    claims: TokenClaims = Depends(require_roles({"owner", "admin"})),
    org_id: str = Depends(get_current_tenant_id),
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
    org_id: str = Depends(get_current_tenant_id),
    service: ToolService = Depends(get_tool_service),
) -> ToolInvokeResponse:
    """Execute a tool with arguments for the tenant."""
    return await service.invoke_tool(organization_id=org_id, request=request)
