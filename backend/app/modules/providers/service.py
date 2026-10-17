"""Provider service and vendor abstraction interfaces."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from backend.app.modules.providers.repository import ProviderCatalogRepository
from backend.app.modules.providers.schemas import CatalogResponse, ProviderOption


class STTProvider(ABC):
    """Abstract interface for speech-to-text providers."""

    @abstractmethod
    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """Stream transcription text from input audio chunks."""


class LLMProvider(ABC):
    """Abstract interface for language model providers."""

    @abstractmethod
    async def generate_stream(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> AsyncIterator[str]:
        """Stream token responses from LLM."""


class TTSProvider(ABC):
    """Abstract interface for text-to-speech providers."""

    @abstractmethod
    async def synthesize_stream(self, text_stream: AsyncIterator[str]) -> AsyncIterator[bytes]:
        """Stream synthesized audio bytes from text tokens."""


class ProviderService:
    """Service providing catalog access and provider metadata."""

    def __init__(self, repository: ProviderCatalogRepository | None = None) -> None:
        self.repository = repository or ProviderCatalogRepository()

    async def get_catalog(self) -> CatalogResponse:
        """Retrieve the complete provider catalog."""
        raw = await self.repository.get_catalog()
        return CatalogResponse(
            stt=[ProviderOption(**item) for item in raw.get("stt", [])],
            llm=[ProviderOption(**item) for item in raw.get("llm", [])],
            tts=[ProviderOption(**item) for item in raw.get("tts", [])],
        )

    async def list_providers_by_type(self, provider_type: str) -> list[ProviderOption]:
        """List provider options filtered by category (stt, llm, or tts)."""
        raw_items = await self.repository.get_by_type(provider_type)
        return [ProviderOption(**item) for item in raw_items]


CatalogService = ProviderService
