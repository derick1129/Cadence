"""Agent repository handling persistence for agents and immutable versions."""

import uuid
from datetime import UTC, datetime
from typing import Any


class AgentRepository:
    """Repository handling persistence for agents and agent versions."""

    def __init__(self, session: Any | None = None) -> None:
        self.session = session
        self._agents: dict[str, dict[str, Any]] = {}
        self._versions: dict[str, dict[str, Any]] = {}

    async def list_agents(self, organization_id: str) -> list[dict[str, Any]]:
        """List all agents belonging to an organization."""
        return [
            agent
            for agent in self._agents.values()
            if agent.get("organization_id") == organization_id
        ]

    async def get_agent_by_id(self, organization_id: str, agent_id: str) -> dict[str, Any] | None:
        """Fetch an agent by ID scoped strictly to the organization."""
        agent = self._agents.get(agent_id)
        if not agent or agent.get("organization_id") != organization_id:
            return None
        return agent

    async def create_agent(self, organization_id: str, name: str) -> dict[str, Any]:
        """Create a new agent row for the specified tenant."""
        now = datetime.now(UTC)
        agent_id = str(uuid.uuid4())
        agent = {
            "id": agent_id,
            "organization_id": organization_id,
            "name": name,
            "current_version_id": None,
            "created_at": now,
            "updated_at": now,
        }
        self._agents[agent_id] = agent
        return agent

    async def set_current_version(
        self, organization_id: str, agent_id: str, version_id: str
    ) -> dict[str, Any] | None:
        """Update current_version_id on an existing agent."""
        agent = await self.get_agent_by_id(organization_id, agent_id)
        if not agent:
            return None
        agent["current_version_id"] = version_id
        agent["updated_at"] = datetime.now(UTC)
        return agent

    async def update_agent_name(
        self, organization_id: str, agent_id: str, name: str
    ) -> dict[str, Any] | None:
        """Update agent name."""
        agent = await self.get_agent_by_id(organization_id, agent_id)
        if not agent:
            return None
        agent["name"] = name
        agent["updated_at"] = datetime.now(UTC)
        return agent

    async def create_version(
        self,
        agent_id: str,
        version_no: int,
        system_prompt: str,
        greeting: str | None,
        stt_config: dict[str, Any],
        llm_config: dict[str, Any],
        tts_config: dict[str, Any],
        silence_timeout_s: int = 15,
        max_duration_s: int = 600,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        """Create an immutable version row for an agent."""
        now = datetime.now(UTC)
        version_id = str(uuid.uuid4())
        version = {
            "id": version_id,
            "agent_id": agent_id,
            "version_no": version_no,
            "system_prompt": system_prompt,
            "greeting": greeting,
            "stt_config": stt_config,
            "llm_config": llm_config,
            "tts_config": tts_config,
            "silence_timeout_s": silence_timeout_s,
            "max_duration_s": max_duration_s,
            "created_by": created_by,
            "created_at": now,
        }
        self._versions[version_id] = version
        return version

    async def get_version_by_id(self, version_id: str) -> dict[str, Any] | None:
        """Fetch a version record by its ID."""
        return self._versions.get(version_id)

    async def list_versions_by_agent_id(self, agent_id: str) -> list[dict[str, Any]]:
        """List all immutable versions for a given agent in ascending version order."""
        versions = [v for v in self._versions.values() if v.get("agent_id") == agent_id]
        versions.sort(key=lambda x: int(x.get("version_no", 0)))
        return versions

    async def get_latest_version_no(self, agent_id: str) -> int:
        """Get the highest version number for an agent."""
        versions = await self.list_versions_by_agent_id(agent_id)
        if not versions:
            return 0
        return max(int(v.get("version_no", 0)) for v in versions)
