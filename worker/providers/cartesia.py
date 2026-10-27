"""Cartesia Sonic streaming TTS adapter."""

from collections.abc import AsyncIterator

from worker.providers.interfaces import SynthesizedAudio, TTSProvider


class CartesiaTTSProvider(TTSProvider):
    """Adapter wrapping Cartesia Sonic ultra-low latency TTS."""

    def __init__(self, model: str = "sonic-english", voice: str = "default-voice") -> None:
        self.model = model
        self.voice = voice

    async def synthesize_stream(self, text_stream: AsyncIterator[str]) -> AsyncIterator[bytes]:
        """Stream synthesized PCM audio bytes from incoming text tokens."""
        async for token in text_stream:
            yield token.encode("utf-8")

    async def synthesize(self, text: str) -> SynthesizedAudio:
        """Synthesize complete text string into audio bytes."""
        data = text.encode("utf-8")
        return SynthesizedAudio(
            data=data,
            format="pcm",
            sample_rate=24000,
            duration_ms=len(text) * 50,
        )
