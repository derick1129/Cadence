"""Agent business logic service."""

from typing import Any

from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.agents.schemas import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
    AgentVersionResponse,
)


class AgentService:
    """Service handling business rules, version bumping, and agent queries."""

    def __init__(self, repository: AgentRepository | None = None) -> None:
        self.repository = repository or AgentRepository()

    async def list_agents(self, organization_id: str) -> list[AgentResponse]:
        """List all agents for an organization with their current pinned version."""
        agents = await self.repository.list_agents(organization_id)
        results: list[AgentResponse] = []
        for agent in agents:
            current_version: AgentVersionResponse | None = None
            if agent.get("current_version_id"):
                raw_version = await self.repository.get_version_by_id(
                    str(agent["current_version_id"])
                )
                if raw_version:
                    current_version = AgentVersionResponse(**raw_version)
            results.append(
                AgentResponse(
                    id=agent["id"],
                    organization_id=agent["organization_id"],
                    name=agent["name"],
                    current_version_id=agent.get("current_version_id"),
                    current_version=current_version,
                    created_at=agent["created_at"],
                    updated_at=agent["updated_at"],
                )
            )
        return results

    async def get_agent(self, organization_id: str, agent_id: str) -> AgentResponse | None:
        """Retrieve an agent by ID scoped to the tenant."""
        agent = await self.repository.get_agent_by_id(organization_id, agent_id)
        if not agent:
            return None
        current_version: AgentVersionResponse | None = None
        if agent.get("current_version_id"):
            raw_version = await self.repository.get_version_by_id(str(agent["current_version_id"]))
            if raw_version:
                current_version = AgentVersionResponse(**raw_version)
        return AgentResponse(
            id=agent["id"],
            organization_id=agent["organization_id"],
            name=agent["name"],
            current_version_id=agent.get("current_version_id"),
            current_version=current_version,
            created_at=agent["created_at"],
            updated_at=agent["updated_at"],
        )

    async def create_agent(
        self,
        organization_id: str,
        data: AgentCreate,
        user_id: str | None = None,
    ) -> AgentResponse:
        """Create a new agent along with its initial version (v1)."""
        agent = await self.repository.create_agent(
            organization_id=organization_id,
            name=data.name,
        )
        version = await self.repository.create_version(
            agent_id=agent["id"],
            version_no=1,
            system_prompt=data.system_prompt,
            greeting=data.greeting,
            stt_config=data.stt_config,
            llm_config=data.llm_config,
            tts_config=data.tts_config,
            silence_timeout_s=data.silence_timeout_s,
            max_duration_s=data.max_duration_s,
            created_by=user_id,
        )
        updated_agent = await self.repository.set_current_version(
            organization_id=organization_id,
            agent_id=agent["id"],
            version_id=version["id"],
        )
        agent_data = updated_agent or agent
        version_resp = AgentVersionResponse(**version)
        return AgentResponse(
            id=agent_data["id"],
            organization_id=agent_data["organization_id"],
            name=agent_data["name"],
            current_version_id=version["id"],
            current_version=version_resp,
            created_at=agent_data["created_at"],
            updated_at=agent_data["updated_at"],
        )

    async def update_agent(
        self,
        organization_id: str,
        agent_id: str,
        data: AgentUpdate,
        user_id: str | None = None,
    ) -> AgentResponse | None:
        """Update agent metadata or create a new immutable version if prompt/configs changed."""
        agent = await self.repository.get_agent_by_id(organization_id, agent_id)
        if not agent:
            return None

        if data.name is not None and data.name != agent["name"]:
            await self.repository.update_agent_name(organization_id, agent_id, data.name)

        has_version_change = any(
            x is not None
            for x in (
                data.system_prompt,
                data.greeting,
                data.stt_config,
                data.llm_config,
                data.tts_config,
                data.silence_timeout_s,
                data.max_duration_s,
            )
        )

        if has_version_change:
            latest_version_dict: dict[str, Any] = {}
            if agent.get("current_version_id"):
                v = await self.repository.get_version_by_id(str(agent["current_version_id"]))
                if v:
                    latest_version_dict = v
            next_version_no = await self.repository.get_latest_version_no(agent_id) + 1
            new_version = await self.repository.create_version(
                agent_id=agent_id,
                version_no=next_version_no,
                system_prompt=data.system_prompt
                if data.system_prompt is not None
                else latest_version_dict.get("system_prompt", ""),
                greeting=data.greeting
                if data.greeting is not None
                else latest_version_dict.get("greeting"),
                stt_config=data.stt_config
                if data.stt_config is not None
                else latest_version_dict.get("stt_config", {}),
                llm_config=data.llm_config
                if data.llm_config is not None
                else latest_version_dict.get("llm_config", {}),
                tts_config=data.tts_config
                if data.tts_config is not None
                else latest_version_dict.get("tts_config", {}),
                silence_timeout_s=data.silence_timeout_s
                if data.silence_timeout_s is not None
                else latest_version_dict.get("silence_timeout_s", 15),
                max_duration_s=data.max_duration_s
                if data.max_duration_s is not None
                else latest_version_dict.get("max_duration_s", 600),
                created_by=user_id,
            )
            await self.repository.set_current_version(organization_id, agent_id, new_version["id"])

        return await self.get_agent(organization_id, agent_id)

    async def list_versions(
        self, organization_id: str, agent_id: str
    ) -> list[AgentVersionResponse]:
        """List all versions for an agent after verifying tenant ownership."""
        agent = await self.repository.get_agent_by_id(organization_id, agent_id)
        if not agent:
            return []
        versions = await self.repository.list_versions_by_agent_id(agent_id)
        return [AgentVersionResponse(**v) for v in versions]

    async def get_version(
        self, organization_id: str, agent_id: str, version_id: str
    ) -> AgentVersionResponse | None:
        """Retrieve a specific version of an agent ensuring tenant ownership."""
        agent = await self.repository.get_agent_by_id(organization_id, agent_id)
        if not agent:
            return None
        version = await self.repository.get_version_by_id(version_id)
        if not version or version.get("agent_id") != agent_id:
            return None
        return AgentVersionResponse(**version)
