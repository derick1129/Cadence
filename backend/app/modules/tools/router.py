"""Tools HTTP router."""

from fastapi import APIRouter, Depends, Header, HTTPException, status

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


@router.get("", response_model=list[ToolResponse])
async def list_tools(
    x_organization_id: str = Header("default-org", alias="X-Organization-Id"),
    service: ToolService = Depends(get_tool_service),
) -> list[ToolResponse]:
    """List all tools registered for the tenant organization."""
    return await service.list_tools(organization_id=x_organization_id)


@router.post("", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def create_tool(
    request: ToolCreate,
    x_organization_id: str = Header("default-org", alias="X-Organization-Id"),
    service: ToolService = Depends(get_tool_service),
) -> ToolResponse:
    """Register a new tool definition for the tenant."""
    return await service.create_tool(organization_id=x_organization_id, data=request)


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(
    tool_id: str,
    x_organization_id: str = Header("default-org", alias="X-Organization-Id"),
    service: ToolService = Depends(get_tool_service),
) -> ToolResponse:
    """Retrieve details for a specific tool."""
    tool = await service.get_tool(organization_id=x_organization_id, tool_id=tool_id)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found",
        )
    return tool


@router.post("/invoke", response_model=ToolInvokeResponse)
async def invoke_tool(
    request: ToolInvokeRequest,
    x_organization_id: str = Header("default-org", alias="X-Organization-Id"),
    service: ToolService = Depends(get_tool_service),
) -> ToolInvokeResponse:
    """Execute a tool with arguments for the tenant."""
    return await service.invoke_tool(organization_id=x_organization_id, request=request)
