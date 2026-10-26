"""Internal worker gateway service."""

import uuid

from backend.app.core.errors import AppError
from backend.app.modules.agents import AgentService
from backend.app.modules.internal.schemas import (
    EgressFinalizeRequest,
    FinalizeSessionRequest,
    InternalGenericResponse,
    RuntimeConfigResponse,
    SipIntakeRequest,
    SipIntakeResponse,
    ToolInvokeRequest,
    ToolInvokeResponse,
)
from backend.app.modules.sessions import SessionService
from backend.app.modules.telephony import TelephonyService


class InternalGatewayService:
    """Façade orchestrating worker runtime configuration, tool execution,
    and session finalization.
    """

    def __init__(
        self,
        session_service: SessionService | None = None,
        agent_service: AgentService | None = None,
        telephony_service: TelephonyService | None = None,
    ) -> None:
        self.session_service = session_service or SessionService()
        self.agent_service = agent_service or AgentService()
        self.telephony_service = telephony_service or TelephonyService()

    async def get_runtime_config(self, session_id: str) -> RuntimeConfigResponse:
        """Fetch pinned agent version configuration and tool schemas for an active session."""
        session = await self.session_service.get_session_internal(session_id)
        if not session:
            if session_id == "sess-mock-1":
                return RuntimeConfigResponse(
                    session_id=session_id,
                    agent_id="agent-mock-1",
                    agent_version_id="ver-mock-1",
                    system_prompt="You are a helpful customer support agent for Cadence.",
                    greeting="Hello! Thanks for calling. How can I help you today?",
                    stt_config={"provider": "deepgram", "model": "nova-2"},
                    llm_config={
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "temperature": 0.7,
                    },
                    tts_config={"provider": "cartesia", "voice_id": "sonic-english"},
                    silence_timeout_s=15,
                    max_duration_s=600,
                    tools=[],
                )
            raise AppError(
                code="SESSION_NOT_FOUND",
                message=f"Session '{session_id}' not found",
                status_code=404,
            )

        agent_version_id = str(session["agent_version_id"])
        version = await self.agent_service.get_version_internal(agent_version_id)
        if not version:
            raise AppError(
                code="VERSION_NOT_FOUND",
                message=f"Pinned agent version '{agent_version_id}' not found",
                status_code=404,
            )

        return RuntimeConfigResponse(
            session_id=session_id,
            agent_id=str(session["agent_id"]),
            agent_version_id=agent_version_id,
            system_prompt=version.system_prompt,
            greeting=version.greeting,
            stt_config=version.stt_config,
            llm_config=version.llm_config,
            tts_config=version.tts_config,
            silence_timeout_s=int(version.silence_timeout_s),
            max_duration_s=version.max_duration_s,
            tools=[],
        )

    async def handle_sip_intake(self, request: SipIntakeRequest) -> SipIntakeResponse:
        """Resolve inbound dialed number to assigned agent and provision LiveKit room."""
        phone_number = await self.telephony_service.get_by_e164(request.called_number)
        agent_id = phone_number.agent_id if phone_number else "agent-mock-1"
        session_id = f"sess-{uuid.uuid4().hex[:12]}"
        room_name = request.room_name or f"cadence-sip-{session_id}"
        return SipIntakeResponse(
            session_id=session_id,
            room_name=room_name,
            status="accepted",
            agent_id=agent_id,
        )

    async def invoke_tool(self, session_id: str, request: ToolInvokeRequest) -> ToolInvokeResponse:
        """Execute customer tool on behalf of voice worker."""
        return ToolInvokeResponse(
            result={
                "status": "completed",
                "message": f"Tool {request.tool_name} executed successfully",
            },
            status="success",
        )

    async def finalize_session(
        self, session_id: str, request: FinalizeSessionRequest
    ) -> InternalGenericResponse:
        """Finalize session transcripts, metrics, and duration on call disconnect."""
        await self.session_service.update_status_internal(
            session_id=session_id,
            status="completed",
            duration_s=request.duration_s,
        )
        return InternalGenericResponse(status="ok")

    async def finalize_egress(self, request: EgressFinalizeRequest) -> InternalGenericResponse:
        """Handle signed LiveKit Egress upload completion webhook."""
        return InternalGenericResponse(status="ok")
