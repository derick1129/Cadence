"""Static provider catalog repository."""

from typing import Any


class ProviderCatalogRepository:
    """Repository serving static catalog data for speech and language model providers."""

    def __init__(self) -> None:
        self._catalog: dict[str, list[dict[str, Any]]] = {
            "stt": [
                {
                    "id": "deepgram",
                    "name": "Deepgram Nova",
                    "provider": "deepgram",
                    "type": "stt",
                    "models": ["nova-2", "nova-3", "nova-2-general", "nova-2-medical"],
                    "voices": [],
                    "default_model": "nova-2",
                    "default_voice": None,
                    "description": "Ultra-low latency streaming speech-to-text.",
                }
            ],
            "llm": [
                {
                    "id": "openai",
                    "name": "OpenAI",
                    "provider": "openai",
                    "type": "llm",
                    "models": ["gpt-4o", "gpt-4o-mini"],
                    "voices": [],
                    "default_model": "gpt-4o-mini",
                    "default_voice": None,
                    "description": "Fast and intelligent conversational language models.",
                },
                {
                    "id": "anthropic",
                    "name": "Anthropic Claude",
                    "provider": "anthropic",
                    "type": "llm",
                    "models": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
                    "voices": [],
                    "default_model": "claude-3-5-sonnet-20241022",
                    "default_voice": None,
                    "description": "High-accuracy steerable LLMs for complex dialogues.",
                },
                {
                    "id": "gemini",
                    "name": "Google Gemini",
                    "provider": "gemini",
                    "type": "llm",
                    "models": ["gemini-1.5-flash", "gemini-1.5-pro"],
                    "voices": [],
                    "default_model": "gemini-1.5-flash",
                    "default_voice": None,
                    "description": "Multimodal and fast token generation models.",
                },
            ],
            "tts": [
                {
                    "id": "cartesia",
                    "name": "Cartesia Sonic",
                    "provider": "cartesia",
                    "type": "tts",
                    "models": ["sonic-english"],
                    "voices": ["sonic-preview", "default-voice", "british-lady"],
                    "default_model": "sonic-english",
                    "default_voice": "default-voice",
                    "description": "Sub-100ms realistic streaming text-to-speech.",
                },
                {
                    "id": "elevenlabs",
                    "name": "ElevenLabs",
                    "provider": "elevenlabs",
                    "type": "tts",
                    "models": ["eleven_turbo_v2_5", "eleven_multilingual_v2"],
                    "voices": ["rachel", "adam", "charlie"],
                    "default_model": "eleven_turbo_v2_5",
                    "default_voice": "rachel",
                    "description": "Expressive voice synthesis with diverse voice clones.",
                },
            ],
        }

    async def get_catalog(self) -> dict[str, list[dict[str, Any]]]:
        """Return the full static catalog."""
        return self._catalog

    async def get_by_type(self, provider_type: str) -> list[dict[str, Any]]:
        """Return provider options for a given category (stt, llm, tts)."""
        return self._catalog.get(provider_type, [])
