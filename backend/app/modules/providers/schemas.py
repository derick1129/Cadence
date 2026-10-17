"""Provider schemas for catalog and configuration."""

from pydantic import BaseModel, ConfigDict, Field


class ProviderOption(BaseModel):
    """Specification of an available AI provider option."""

    id: str
    name: str
    provider: str
    type: str  # "stt", "llm", "tts"
    models: list[str] = Field(default_factory=list)
    voices: list[str] = Field(default_factory=list)
    default_model: str | None = None
    default_voice: str | None = None
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CatalogResponse(BaseModel):
    """Full catalog response containing available STT, LLM, and TTS providers."""

    stt: list[ProviderOption]
    llm: list[ProviderOption]
    tts: list[ProviderOption]

    model_config = ConfigDict(from_attributes=True)
