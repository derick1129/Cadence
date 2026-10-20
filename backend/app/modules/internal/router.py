"""Internal worker and webhook router."""

from fastapi import APIRouter, Depends, Header, HTTPException, status

from backend.app.core.security import compare_digest
from backend.app.core.settings import settings
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
