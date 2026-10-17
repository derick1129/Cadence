"""Agent HTTP router."""

from fastapi import APIRouter, Depends, Header, HTTPException, status

from backend.app.modules.agents.schemas import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
    AgentVersionResponse,
)
from backend.app.modules.agents.service import AgentService

router = APIRouter(prefix="/agents", tags=["agents"])


def get_agent_service() -> AgentService:
    """Dependency provider returning an AgentService instance."""
    return AgentService()


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    x_organization_id: str = Header("default-org", alias="X-Organization-Id"),
    service: AgentService = Depends(get_agent_service),
) -> list[AgentResponse]:
    """List all voice agents for the current organization."""
    return await service.list_agents(organization_id=x_organization_id)


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    request: AgentCreate,
    x_organization_id: str = Header("default-org", alias="X-Organization-Id"),
    service: AgentService = Depends(get_agent_service),
) -> AgentResponse:
    """Create a new voice agent with initial version."""
    return await service.create_agent(organization_id=x_organization_id, data=request)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    x_organization_id: str = Header("default-org", alias="X-Organization-Id"),
    service: AgentService = Depends(get_agent_service),
) -> AgentResponse:
    """Get an agent by ID scoped to the organization."""
    agent = await service.get_agent(organization_id=x_organization_id, agent_id=agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return agent


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    request: AgentUpdate,
    x_organization_id: str = Header("default-org", alias="X-Organization-Id"),
    service: AgentService = Depends(get_agent_service),
) -> AgentResponse:
    """Update agent metadata or bump to a new immutable version."""
    agent = await service.update_agent(
        organization_id=x_organization_id,
        agent_id=agent_id,
        data=request,
    )
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return agent


@router.get("/{agent_id}/versions", response_model=list[AgentVersionResponse])
async def list_agent_versions(
    agent_id: str,
    x_organization_id: str = Header("default-org", alias="X-Organization-Id"),
    service: AgentService = Depends(get_agent_service),
) -> list[AgentVersionResponse]:
    """List all version revisions for an agent."""
    agent = await service.get_agent(organization_id=x_organization_id, agent_id=agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return await service.list_versions(organization_id=x_organization_id, agent_id=agent_id)


@router.get("/{agent_id}/versions/{version_id}", response_model=AgentVersionResponse)
async def get_agent_version(
    agent_id: str,
    version_id: str,
    x_organization_id: str = Header("default-org", alias="X-Organization-Id"),
    service: AgentService = Depends(get_agent_service),
) -> AgentVersionResponse:
    """Retrieve a specific version of an agent."""
    version = await service.get_version(
        organization_id=x_organization_id,
        agent_id=agent_id,
        version_id=version_id,
    )
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent version not found",
        )
    return version
