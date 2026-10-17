"""Provider catalog HTTP router."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.modules.providers.schemas import CatalogResponse, ProviderOption
from backend.app.modules.providers.service import ProviderService

router = APIRouter(prefix="/providers", tags=["providers"])


def get_provider_service() -> ProviderService:
    """Dependency provider returning a ProviderService instance."""
    return ProviderService()


@router.get("", response_model=CatalogResponse)
async def get_providers(
    service: ProviderService = Depends(get_provider_service),
) -> CatalogResponse:
    """Return available AI model, voice, and speech providers."""
    return await service.get_catalog()


@router.get("/catalog", response_model=CatalogResponse)
async def get_catalog(
    service: ProviderService = Depends(get_provider_service),
) -> CatalogResponse:
    """Return the complete AI model and voice catalog."""
    return await service.get_catalog()


@router.get("/{provider_type}", response_model=list[ProviderOption])
async def list_providers_by_type(
    provider_type: str,
    service: ProviderService = Depends(get_provider_service),
) -> list[ProviderOption]:
    """Return providers filtered by provider type (stt, llm, tts)."""
    normalized = provider_type.lower()
    if normalized not in {"stt", "llm", "tts"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid provider type. Must be one of: stt, llm, tts",
        )
    return await service.list_providers_by_type(normalized)
