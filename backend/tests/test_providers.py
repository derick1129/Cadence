"""Tests for the providers module including static catalog, interfaces, and router."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.modules.providers import (
    CatalogResponse,
    CatalogService,
    LLMProvider,
    ProviderService,
    STTProvider,
    TTSProvider,
    router,
)


@pytest.fixture
def provider_service() -> ProviderService:
    """Fixture providing ProviderService."""
    return ProviderService()


@pytest.fixture
def provider_app() -> FastAPI:
    """FastAPI test app containing providers router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_provider_catalog_content(provider_service: ProviderService) -> None:
    """Verify that catalog returns required STT, LLM, and TTS providers."""
    catalog = await provider_service.get_catalog()
    assert isinstance(catalog, CatalogResponse)

    # Verify STT contains Deepgram
    stt_ids = [p.id for p in catalog.stt]
    assert "deepgram" in stt_ids
    deepgram = next(p for p in catalog.stt if p.id == "deepgram")
    assert "nova-2" in deepgram.models

    # Verify LLM contains OpenAI, Anthropic, Gemini
    llm_ids = [p.id for p in catalog.llm]
    assert "openai" in llm_ids
    assert "anthropic" in llm_ids
    assert "gemini" in llm_ids

    # Verify TTS contains Cartesia and ElevenLabs
    tts_ids = [p.id for p in catalog.tts]
    assert "cartesia" in tts_ids
    assert "elevenlabs" in tts_ids


@pytest.mark.asyncio
async def test_provider_filtering(provider_service: ProviderService) -> None:
    """Verify listing providers filtered by type."""
    stt_list = await provider_service.list_providers_by_type("stt")
    assert all(p.type == "stt" for p in stt_list)

    llm_list = await provider_service.list_providers_by_type("llm")
    assert all(p.type == "llm" for p in llm_list)

    tts_list = await provider_service.list_providers_by_type("tts")
    assert all(p.type == "tts" for p in tts_list)


def test_provider_interfaces_exportable() -> None:
    """Ensure abstract provider interfaces exist and are subclassable."""
    assert issubclass(STTProvider, object)
    assert issubclass(LLMProvider, object)
    assert issubclass(TTSProvider, object)
    assert CatalogService is ProviderService


@pytest.mark.asyncio
async def test_provider_router_http(provider_app: FastAPI) -> None:
    """Test HTTP endpoints for provider catalog and type filtering."""
    transport = ASGITransport(app=provider_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Get full catalog
        resp = await client.get("/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert "stt" in data
        assert "llm" in data
        assert "tts" in data

        # Get catalog alias
        cat_resp = await client.get("/providers/catalog")
        assert cat_resp.status_code == 200

        # Filter by LLM
        llm_resp = await client.get("/providers/llm")
        assert llm_resp.status_code == 200
        llms = llm_resp.json()
        assert len(llms) >= 3

        # Invalid provider type returns 400
        inv_resp = await client.get("/providers/invalid-type")
        assert inv_resp.status_code == 400
