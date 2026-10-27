"""Agent repository handling persistence for agents and immutable versions."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.agents.models import Agent, AgentVersion


class AgentRepository:
    """Repository handling persistence for agents and immutable versions."""

    _shared_agents: dict[str, dict[str, Any]] = {}
    _shared_versions: dict[str, dict[str, Any]] = {}

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self._agents = self._shared_agents
        self._versions = self._shared_versions

    async def list_agents(self, organization_id: str) -> list[dict[str, Any]]:
        """List all agents belonging to an organization."""
        if self.session is not None:
            try:
                org_uuid = uuid.UUID(organization_id)
            except ValueError:
                return []
            result = await self.session.execute(
                select(Agent)
                .where(Agent.organization_id == org_uuid)
                .order_by(desc(Agent.created_at))
            )
            records = result.scalars().all()
            return [
                {
                    "id": str(r.id),
                    "organization_id": str(r.organization_id),
                    "name": r.name,
                    "current_version_id": (
                        str(r.current_version_id) if r.current_version_id else None
                    ),
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
                for r in records
            ]
        return [
            agent
            for agent in self._agents.values()
            if agent.get("organization_id") == organization_id
        ]

    async def get_agent_by_id(self, organization_id: str, agent_id: str) -> dict[str, Any] | None:
        """Fetch an agent by ID scoped strictly to the organization."""
        if self.session is not None:
            try:
                org_uuid = uuid.UUID(organization_id)
                agent_uuid = uuid.UUID(agent_id)
            except ValueError:
                return None
            result = await self.session.execute(
                select(Agent).where(
                    Agent.id == agent_uuid,
                    Agent.organization_id == org_uuid,
                )
            )
            record = result.scalar_one_or_none()
            if not record:
                return None
            return {
                "id": str(record.id),
                "organization_id": str(record.organization_id),
                "name": record.name,
                "current_version_id": (
                    str(record.current_version_id) if record.current_version_id else None
                ),
                "created_at": record.created_at,
                "updated_at": record.updated_at,
            }
        agent = self._agents.get(agent_id)
        if not agent or agent.get("organization_id") != organization_id:
            return None
        return agent

    async def create_agent(self, organization_id: str, name: str) -> dict[str, Any]:
        """Create a new agent row for the specified tenant."""
        now = datetime.now(UTC)
        if self.session is not None:
            org_uuid = uuid.UUID(organization_id)
            agent = Agent(organization_id=org_uuid, name=name)
            self.session.add(agent)
            await self.session.flush()
            return {
                "id": str(agent.id),
                "organization_id": str(agent.organization_id),
                "name": agent.name,
                "current_version_id": None,
                "created_at": agent.created_at,
                "updated_at": agent.updated_at,
            }
        agent_id = str(uuid.uuid4())
        agent_dict = {
            "id": agent_id,
            "organization_id": organization_id,
            "name": name,
            "current_version_id": None,
            "created_at": now,
            "updated_at": now,
        }
        self._agents[agent_id] = agent_dict
        return agent_dict

    async def set_current_version(
        self, organization_id: str, agent_id: str, version_id: str
    ) -> dict[str, Any] | None:
        """Update current_version_id on an existing agent."""
        if self.session is not None:
            try:
                org_uuid = uuid.UUID(organization_id)
                agent_uuid = uuid.UUID(agent_id)
                ver_uuid = uuid.UUID(version_id)
            except ValueError:
                return None
            await self.session.execute(
                update(Agent)
                .where(Agent.id == agent_uuid, Agent.organization_id == org_uuid)
                .values(current_version_id=ver_uuid, updated_at=datetime.now(UTC))
            )
            await self.session.flush()
            return await self.get_agent_by_id(organization_id, agent_id)

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
        if self.session is not None:
            try:
                org_uuid = uuid.UUID(organization_id)
                agent_uuid = uuid.UUID(agent_id)
            except ValueError:
                return None
            await self.session.execute(
                update(Agent)
                .where(Agent.id == agent_uuid, Agent.organization_id == org_uuid)
                .values(name=name, updated_at=datetime.now(UTC))
            )
            await self.session.flush()
            return await self.get_agent_by_id(organization_id, agent_id)

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
        if self.session is not None:
            agent_uuid = uuid.UUID(agent_id)
            user_uuid = uuid.UUID(created_by) if created_by else None
            version = AgentVersion(
                agent_id=agent_uuid,
                version_no=version_no,
                system_prompt=system_prompt,
                greeting=greeting,
                stt_config=stt_config,
                llm_config=llm_config,
                tts_config=tts_config,
                silence_timeout_s=silence_timeout_s,
                max_duration_s=max_duration_s,
                created_by=user_uuid,
            )
            self.session.add(version)
            await self.session.flush()
            return {
                "id": str(version.id),
                "agent_id": str(version.agent_id),
                "version_no": version.version_no,
                "system_prompt": version.system_prompt,
                "greeting": version.greeting,
                "stt_config": version.stt_config,
                "llm_config": version.llm_config,
                "tts_config": version.tts_config,
                "silence_timeout_s": version.silence_timeout_s,
                "max_duration_s": version.max_duration_s,
                "created_by": str(version.created_by) if version.created_by else None,
                "created_at": version.created_at,
            }

        version_id = str(uuid.uuid4())
        ver_dict = {
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
        self._versions[version_id] = ver_dict
        return ver_dict

    async def get_version_by_id(self, version_id: str) -> dict[str, Any] | None:
        """Fetch a version record by its ID."""
        if self.session is not None:
            try:
                ver_uuid = uuid.UUID(version_id)
            except ValueError:
                return None
            result = await self.session.execute(
                select(AgentVersion).where(AgentVersion.id == ver_uuid)
            )
            v = result.scalar_one_or_none()
            if not v:
                return None
            return {
                "id": str(v.id),
                "agent_id": str(v.agent_id),
                "version_no": v.version_no,
                "system_prompt": v.system_prompt,
                "greeting": v.greeting,
                "stt_config": v.stt_config,
                "llm_config": v.llm_config,
                "tts_config": v.tts_config,
                "silence_timeout_s": v.silence_timeout_s,
                "max_duration_s": v.max_duration_s,
                "created_by": str(v.created_by) if v.created_by else None,
                "created_at": v.created_at,
            }
        return self._versions.get(version_id) or self._versions.get(version_id.lower())

    async def list_versions_by_agent_id(self, agent_id: str) -> list[dict[str, Any]]:
        """List all immutable versions for a given agent in ascending version order."""
        if self.session is not None:
            try:
                agent_uuid = uuid.UUID(agent_id)
            except ValueError:
                return []
            result = await self.session.execute(
                select(AgentVersion)
                .where(AgentVersion.agent_id == agent_uuid)
                .order_by(AgentVersion.version_no.asc())
            )
            records = result.scalars().all()
            return [
                {
                    "id": str(v.id),
                    "agent_id": str(v.agent_id),
                    "version_no": v.version_no,
                    "system_prompt": v.system_prompt,
                    "greeting": v.greeting,
                    "stt_config": v.stt_config,
                    "llm_config": v.llm_config,
                    "tts_config": v.tts_config,
                    "silence_timeout_s": v.silence_timeout_s,
                    "max_duration_s": v.max_duration_s,
                    "created_by": str(v.created_by) if v.created_by else None,
                    "created_at": v.created_at,
                }
                for v in records
            ]
        versions = [v for v in self._versions.values() if v.get("agent_id") == agent_id]
        versions.sort(key=lambda x: int(x.get("version_no", 0)))
        return versions

    async def get_latest_version_no(self, agent_id: str) -> int:
        """Get the highest version number for an agent."""
        if self.session is not None:
            try:
                agent_uuid = uuid.UUID(agent_id)
            except ValueError:
                return 0
            result = await self.session.execute(
                select(AgentVersion.version_no)
                .where(AgentVersion.agent_id == agent_uuid)
                .order_by(desc(AgentVersion.version_no))
                .limit(1)
            )
            val = result.scalar_one_or_none()
            return val if val is not None else 0
        versions = await self.list_versions_by_agent_id(agent_id)
        if not versions:
            return 0
        return max(int(v.get("version_no", 0)) for v in versions)
