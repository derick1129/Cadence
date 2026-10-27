import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status

from backend.app.core.livekit import generate_livekit_token
from backend.app.core.security import compare_digest
from backend.app.core.settings import settings
from backend.app.modules.internal.schemas import (
    EgressFinalizeRequest,
    FinalizeSessionRequest,
    InternalGenericResponse,
    RuntimeConfigResponse,
    SipInboundRequest,
    SipInboundResponse,
    SipIntakeRequest,
    SipIntakeResponse,
    ToolInvokeRequest,
    ToolInvokeResponse,
)
from backend.app.modules.internal.service import InternalGatewayService

router = APIRouter(prefix="/internal", tags=["internal"])


async def verify_internal_token(
    x_internal_service_token: str | None = Header(None, alias="X-Internal-Service-Token"),
) -> None:
    """Verify internal worker service token using constant-time comparison."""
    if not x_internal_service_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing internal service token",
        )
    if not compare_digest(x_internal_service_token, settings.INTERNAL_SERVICE_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal service token",
        )


def get_internal_service() -> InternalGatewayService:
    """Dependency provider for InternalGatewayService."""
    return InternalGatewayService()


@router.get(
    "/sessions/{id}/runtime-config",
    response_model=RuntimeConfigResponse,
    dependencies=[Depends(verify_internal_token)],
)
async def get_runtime_config(
    id: str,
    service: InternalGatewayService = Depends(get_internal_service),
) -> RuntimeConfigResponse:
    """Fetch runtime configuration for voice worker initializing session."""
    return await service.get_runtime_config(id)


@router.post(
    "/sessions/intake",
    response_model=SipIntakeResponse,
    dependencies=[Depends(verify_internal_token)],
)
async def sip_intake(
    request: SipIntakeRequest,
    service: InternalGatewayService = Depends(get_internal_service),
) -> SipIntakeResponse:
    """Resolve dialed SIP number to agent and return room configuration."""
    return await service.handle_sip_intake(request)


@router.post(
    "/sip/inbound",
    response_model=SipInboundResponse,
    dependencies=[Depends(verify_internal_token)],
)
async def handle_sip_inbound(
    request: SipInboundRequest,
    service: InternalGatewayService = Depends(get_internal_service),
) -> SipInboundResponse:
    """LiveKit SIP inbound call intake. Maps dialed E.164 to agent and initiates session."""
    telephony_service = service.telephony_service
    agent_repo = service.agent_service.repository
    session_repo = service.session_service.repository

    phone_record = await telephony_service.get_by_e164(request.called_e164)
    if not phone_record or not phone_record.agent_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No agent assigned to this phone number",
        )

    agent = await agent_repo.get_agent_by_id(
        str(phone_record.organization_id), str(phone_record.agent_id)
    )
    current_version_id = (
        (
            agent.get("current_version_id")
            if isinstance(agent, dict)
            else getattr(agent, "current_version_id", None)
        )
        if agent
        else None
    )
    if not agent or not current_version_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configured agent has no active version",
        )

    session_id = uuid.uuid4()
    room_name = f"cadence-phone-{session_id}"

    new_session = await session_repo.create_session(
        organization_id=str(phone_record.organization_id),
        agent_id=str(phone_record.agent_id),
        agent_version_id=str(current_version_id),
        channel="phone",
        room_name=room_name,
    )
    new_session_id = str(
        new_session["id"]
        if isinstance(new_session, dict)
        else getattr(new_session, "id", session_id)
    )

    livekit_token = generate_livekit_token(
        room_name=room_name,
        participant_identity=f"phone-{request.caller_e164}",
        session_id=new_session_id,
    )

    return SipInboundResponse(
        session_id=new_session_id,
        room_name=room_name,
        livekit_token=livekit_token,
        livekit_url=settings.livekit_url,
        channel="phone",
        agent_id=str(phone_record.agent_id),
    )


@router.post(
    "/sessions/{id}/tools/invoke",
    response_model=ToolInvokeResponse,
    dependencies=[Depends(verify_internal_token)],
)
async def invoke_tool(
    id: str,
    request: ToolInvokeRequest,
    service: InternalGatewayService = Depends(get_internal_service),
) -> ToolInvokeResponse:
    """Execute customer tool on behalf of voice worker."""
    return await service.invoke_tool(id, request)


@router.post(
    "/sessions/{id}/finalize",
    response_model=InternalGenericResponse,
    dependencies=[Depends(verify_internal_token)],
)
async def finalize_session(
    id: str,
    request: FinalizeSessionRequest,
    service: InternalGatewayService = Depends(get_internal_service),
) -> InternalGenericResponse:
    """Finalize session transcripts, metrics, and duration on call disconnect."""
    return await service.finalize_session(id, request)


@router.post(
    "/egress/finalize",
    response_model=InternalGenericResponse,
    dependencies=[Depends(verify_internal_token)],
)
async def finalize_egress(
    request: EgressFinalizeRequest,
    service: InternalGatewayService = Depends(get_internal_service),
) -> InternalGenericResponse:
    """Handle signed LiveKit Egress upload completion webhook."""
    return await service.finalize_egress(request)
