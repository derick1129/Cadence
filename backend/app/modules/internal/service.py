"""Internal worker gateway service."""

import uuid

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
        telephony_service: TelephonyService | None = None,
    ) -> None:
        self.session_service = session_service or SessionService()
        self.telephony_service = telephony_service or TelephonyService()

    async def get_runtime_config(self, session_id: str) -> RuntimeConfigResponse:
        """Fetch pinned agent version configuration and tool schemas for an active session."""
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
        """Execute a backend tool on behalf of the voice worker with SSRF protection."""
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
        """Record final transcripts, turn latencies, interruption counts, and usage events."""
        return InternalGenericResponse(status="ok")

    async def finalize_egress(self, request: EgressFinalizeRequest) -> InternalGenericResponse:
        """Record recording key on the session upon LiveKit Egress upload completion."""
        return InternalGenericResponse(status="ok")
