"""LiveKit voice agent worker entrypoint and job dispatcher.

Stateless worker executing one voice conversation per LiveKit room. Fetches pinned
runtime configuration from the backend control plane and streams audio turns.
"""

import logging
from collections.abc import Awaitable, Callable

import httpx
from livekit.agents import JobContext, WorkerOptions, cli
from pydantic import BaseModel, Field

logger = logging.getLogger("cadence.worker")


class WorkerConfig(BaseModel):
    """Configuration settings for the voice agent worker process."""

    livekit_url: str = Field(default="ws://localhost:7880", description="LiveKit WS/RTC URL")
    livekit_api_key: str = Field(default="devkey", description="LiveKit API key")
    livekit_api_secret: str = Field(default="secret", description="LiveKit API secret")
    backend_internal_url: str = Field(
        default="http://localhost:8000/internal",
        description="Base URL for backend internal service endpoints",
    )
    internal_service_token: str = Field(
        default="cadence-default-internal-token",
        description="Shared secret for internal service token authentication",
    )
    agent_name: str = Field(
        default="cadence-voice-agent",
        description="Agent name registered with LiveKit server",
    )


class RuntimeConfig(BaseModel):
    """Pinned runtime configuration for a specific session."""

    session_id: str = Field(description="Unique session identifier")
    agent_id: str = Field(description="Parent agent identifier")
    agent_version_id: str = Field(description="Pinned immutable agent version identifier")
    system_prompt: str = Field(description="System instructions for the conversation")
    greeting: str | None = Field(default=None, description="Initial spoken greeting")
    stt_config: dict[str, object] = Field(
        default_factory=dict, description="Speech-to-text provider settings"
    )
    llm_config: dict[str, object] = Field(
        default_factory=dict, description="Language model provider settings"
    )
    tts_config: dict[str, object] = Field(
        default_factory=dict, description="Text-to-speech provider settings"
    )
    silence_timeout_s: float = Field(default=10.0, description="Silence timeout threshold")
    max_duration_s: int = Field(default=3600, description="Maximum call duration in seconds")


async def fetch_runtime_config(
    session_id: str,
    config: WorkerConfig,
    client: httpx.AsyncClient | None = None,
) -> RuntimeConfig:
    """Fetch session-pinned runtime configuration from backend internal API."""
    url = f"{config.backend_internal_url.rstrip('/')}/sessions/{session_id}/runtime-config"
    headers = {"X-Internal-Service-Token": config.internal_service_token}

    if client is not None:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return RuntimeConfig.model_validate(response.json())

    async with httpx.AsyncClient(timeout=10.0) as local_client:
        response = await local_client.get(url, headers=headers)
        response.raise_for_status()
        return RuntimeConfig.model_validate(response.json())


def extract_session_id(room_name: str, room_metadata: str | None) -> str:
    """Extract or fall back to room name for session identification."""
    if room_metadata and room_metadata.strip():
        return room_metadata.strip()
    return room_name


async def entrypoint(ctx: JobContext) -> None:
    """Main job dispatch handler executed for every incoming LiveKit room job."""
    await ctx.connect()
    worker_cfg = WorkerConfig()
    session_id = extract_session_id(ctx.room.name, ctx.room.metadata)
    logger.info("Worker dispatched for room %s (session: %s)", ctx.room.name, session_id)

    try:
        runtime_cfg = await fetch_runtime_config(session_id, worker_cfg)
        logger.info(
            "Runtime config loaded for session %s (version: %s)",
            runtime_cfg.session_id,
            runtime_cfg.agent_version_id,
        )
    except Exception as exc:
        logger.error("Failed to load runtime config for session %s: %s", session_id, exc)
        return


def create_worker_options(
    entrypoint_fnc: Callable[[JobContext], Awaitable[None]] | None = None,
    config: WorkerConfig | None = None,
) -> WorkerOptions:
    """Construct configured WorkerOptions for the LiveKit runner CLI."""
    cfg = config or WorkerConfig()
    handler = entrypoint_fnc or entrypoint
    return WorkerOptions(
        entrypoint_fnc=handler,
        ws_url=cfg.livekit_url,
        api_key=cfg.livekit_api_key,
        api_secret=cfg.livekit_api_secret,
        agent_name=cfg.agent_name,
    )


def run_worker() -> None:
    """Start the LiveKit agent worker process using CLI runner."""
    cli.run_app(create_worker_options())
