"""Agent business logic service."""

import uuid
from typing import Any

from backend.app.core.errors import AppError
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.agents.schemas import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
    AgentVersionResponse,
)
from backend.app.modules.providers import ProviderOption, ProviderService

DEFAULT_STT_CONFIG = {"provider": "deepgram", "model": "nova-2"}
DEFAULT_LLM_CONFIG = {"provider": "openai", "model": "gpt-4o-mini"}
DEFAULT_TTS_CONFIG = {"provider": "cartesia", "model": "sonic-english", "voice": "default-voice"}


def _canonical_uuid(val: Any) -> str:
    """Normalize a UUID string or UUID object to canonical lowercase hex format."""
    if not val:
        return ""
    try:
        return str(uuid.UUID(str(val)))
    except (ValueError, TypeError, AttributeError):
        return str(val).strip().lower()


class AgentService:
    """Service handling business rules, version bumping, and agent queries."""

    def __init__(
        self,
        repository: AgentRepository | None = None,
        provider_service: ProviderService | None = None,
    ) -> None:
        self.repository = repository or AgentRepository()
        self.provider_service = provider_service or ProviderService()

    def _build_response(
        self, agent: dict[str, Any], version: dict[str, Any] | None = None
    ) -> AgentResponse:
        v_resp = AgentVersionResponse(**version) if version else None
        return AgentResponse(
            id=agent["id"],
            organization_id=agent["organization_id"],
            name=agent["name"],
            current_version_id=agent.get("current_version_id"),
            current_version=v_resp,
            created_at=agent["created_at"],
            updated_at=agent["updated_at"],
        )

    async def _get_agent_record(
        self, organization_id: str, agent_id: str
    ) -> tuple[dict[str, Any] | None, str]:
        canon = _canonical_uuid(agent_id)
        rec = await self.repository.get_agent_by_id(organization_id, agent_id)
        if not rec and canon != agent_id:
            rec = await self.repository.get_agent_by_id(organization_id, canon)
        return rec, canon

    def _validate_tts_voice(
        self,
        cfg: dict[str, Any],
        opt: ProviderOption,
        default_config: dict[str, Any],
    ) -> str | None:
        voice = cfg.get("voice")
        if not voice:
            if opt.provider == default_config.get("provider") and default_config.get("voice"):
                voice = default_config["voice"]
            else:
                voice = opt.default_voice or (opt.voices[0] if opt.voices else None)
        if opt.voices and (not voice or voice not in opt.voices):
            raise AppError(
                code="INVALID_PROVIDER_CONFIG",
                message=(
                    f"TTS voice '{voice}' is not supported by provider '{opt.provider}'. "
                    f"Supported: {sorted(opt.voices)}"
                ),
                status_code=400,
            )
        return voice

    def _validate_category_config(
        self,
        category: str,
        config: dict[str, Any] | None,
        default_config: dict[str, Any],
        catalog_providers: list[ProviderOption],
    ) -> dict[str, Any]:
        cfg = dict(config or {})
        prov = (
            cfg["provider"]
            if "provider" in cfg and not cfg["provider"]
            else (cfg.get("provider") or default_config.get("provider"))
        )
        if not prov:
            raise AppError(
                code="INVALID_PROVIDER_CONFIG",
                message=f"{category} provider is required.",
                status_code=400,
            )
        opt = next((p for p in catalog_providers if p.provider == prov or p.id == prov), None)
        if not opt:
            supported = sorted({p.provider for p in catalog_providers})
            raise AppError(
                code="INVALID_PROVIDER_CONFIG",
                message=f"{category} provider '{prov}' is not in catalog. Supported: {supported}",
                status_code=400,
            )
        def_m = (
            default_config.get("model")
            if opt.provider == default_config.get("provider")
            else opt.default_model
        )
        model = cfg["model"] if "model" in cfg and not cfg["model"] else (cfg.get("model") or def_m)
        if not model or model not in opt.models:
            raise AppError(
                code="INVALID_PROVIDER_CONFIG",
                message=(
                    f"{category} model '{model}' is not supported by provider '{opt.provider}'. "
                    f"Supported: {sorted(opt.models)}"
                ),
                status_code=400,
            )
        res = {**cfg, "provider": opt.provider, "model": model}
        if category == "TTS":
            voice = self._validate_tts_voice(cfg, opt, default_config)
            if voice is not None:
                res["voice"] = voice
        return res

    async def _validate_configs(
        self,
        stt_config: dict[str, Any] | None,
        llm_config: dict[str, Any] | None,
        tts_config: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        catalog = await self.provider_service.get_catalog()
        stt = self._validate_category_config("STT", stt_config, DEFAULT_STT_CONFIG, catalog.stt)
        llm = self._validate_category_config("LLM", llm_config, DEFAULT_LLM_CONFIG, catalog.llm)
        tts = self._validate_category_config("TTS", tts_config, DEFAULT_TTS_CONFIG, catalog.tts)
        return stt, llm, tts

    async def list_agents(self, organization_id: str) -> list[AgentResponse]:
        agents = await self.repository.list_agents(organization_id)
        results: list[AgentResponse] = []
        for agent in agents:
            raw_v = (
                await self.repository.get_version_by_id(str(agent["current_version_id"]))
                if agent.get("current_version_id")
                else None
            )
            results.append(self._build_response(agent, raw_v))
        return results

    async def get_agent(self, organization_id: str, agent_id: str) -> AgentResponse | None:
        agent, _ = await self._get_agent_record(organization_id, agent_id)
        if not agent:
            return None
        raw_v = (
            await self.repository.get_version_by_id(str(agent["current_version_id"]))
            if agent.get("current_version_id")
            else None
        )
        return self._build_response(agent, raw_v)

    async def create_agent(
        self, organization_id: str, data: AgentCreate, user_id: str | None = None
    ) -> AgentResponse:
        stt, llm, tts = await self._validate_configs(
            data.stt_config, data.llm_config, data.tts_config
        )
        agent = await self.repository.create_agent(organization_id=organization_id, name=data.name)
        version = await self.repository.create_version(
            agent_id=agent["id"],
            version_no=1,
            system_prompt=data.system_prompt,
            greeting=data.greeting,
            stt_config=stt,
            llm_config=llm,
            tts_config=tts,
            silence_timeout_s=data.silence_timeout_s,
            max_duration_s=data.max_duration_s,
            created_by=user_id,
        )
        updated = await self.repository.set_current_version(
            organization_id=organization_id, agent_id=agent["id"], version_id=version["id"]
        )
        return self._build_response(updated or agent, version)

    async def _create_next_version(
        self,
        target_id: str,
        data: AgentUpdate,
        stt: dict[str, Any],
        llm: dict[str, Any],
        tts: dict[str, Any],
        latest: dict[str, Any],
        user_id: str | None,
    ) -> dict[str, Any]:
        next_ver = await self.repository.get_latest_version_no(target_id) + 1
        prompt = (
            data.system_prompt
            if data.system_prompt is not None
            else latest.get("system_prompt", "")
        )
        return await self.repository.create_version(
            agent_id=target_id,
            version_no=next_ver,
            system_prompt=prompt,
            greeting=data.greeting if data.greeting is not None else latest.get("greeting"),
            stt_config=stt,
            llm_config=llm,
            tts_config=tts,
            silence_timeout_s=(
                data.silence_timeout_s
                if data.silence_timeout_s is not None
                else latest.get("silence_timeout_s", 15)
            ),
            max_duration_s=(
                data.max_duration_s
                if data.max_duration_s is not None
                else latest.get("max_duration_s", 600)
            ),
            created_by=user_id,
        )

    async def update_agent(
        self,
        organization_id: str,
        agent_id: str,
        data: AgentUpdate,
        user_id: str | None = None,
    ) -> AgentResponse | None:
        agent, _ = await self._get_agent_record(organization_id, agent_id)
        if not agent:
            return None

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
        stt, llm, tts = None, None, None
        latest: dict[str, Any] = {}

        if has_version_change:
            if agent.get("current_version_id"):
                v = await self.repository.get_version_by_id(str(agent["current_version_id"]))
                if v:
                    latest = v
            stt, llm, tts = await self._validate_configs(
                data.stt_config if data.stt_config is not None else latest.get("stt_config", {}),
                data.llm_config if data.llm_config is not None else latest.get("llm_config", {}),
                data.tts_config if data.tts_config is not None else latest.get("tts_config", {}),
            )

        target_id = agent["id"]
        if data.name is not None and data.name != agent["name"]:
            await self.repository.update_agent_name(organization_id, target_id, data.name)

        if has_version_change and stt is not None and llm is not None and tts is not None:
            new_v = await self._create_next_version(target_id, data, stt, llm, tts, latest, user_id)
            await self.repository.set_current_version(organization_id, target_id, new_v["id"])

        return await self.get_agent(organization_id, target_id)

    async def list_versions(
        self, organization_id: str, agent_id: str
    ) -> list[AgentVersionResponse]:
        agent, _ = await self._get_agent_record(organization_id, agent_id)
        if not agent:
            return []
        versions = await self.repository.list_versions_by_agent_id(agent["id"])
        return [AgentVersionResponse(**v) for v in versions]

    async def get_version(
        self, organization_id: str, agent_id: str, version_id: str
    ) -> AgentVersionResponse | None:
        agent, canon = await self._get_agent_record(organization_id, agent_id)
        if not agent:
            return None
        canon_v = _canonical_uuid(version_id)
        version = await self.repository.get_version_by_id(canon_v or version_id)
        if not version or _canonical_uuid(version.get("agent_id")) != canon:
            return None
        return AgentVersionResponse(**version)

    async def get_version_internal(self, version_id: str) -> AgentVersionResponse | None:
        """Fetch an agent version by ID for internal worker gateway configuration."""
        canon_v = _canonical_uuid(version_id)
        version = await self.repository.get_version_by_id(canon_v or version_id)
        if not version:
            return None
        return AgentVersionResponse(**version)
