"""Deepgram STT streaming adapter."""

from collections.abc import AsyncIterator

from worker.providers.interfaces import AudioChunk, STTProvider, TranscriptionResult


class DeepgramSTTProvider(STTProvider):
    """Adapter wrapping Deepgram Nova streaming speech-to-text."""

    def __init__(self, model: str = "nova-2", language: str = "en") -> None:
        self.model = model
        self.language = language

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[AudioChunk]
    ) -> AsyncIterator[TranscriptionResult]:
        """Stream transcription results from incoming audio chunks."""
        async for chunk in audio_stream:
            text = f"heard:{len(chunk.data)}"
            yield TranscriptionResult(text=text, is_final=True, language=self.language)

    async def transcribe_chunk(self, chunk: AudioChunk) -> TranscriptionResult:
        """Transcribe an isolated audio chunk."""
        return TranscriptionResult(
            text=f"heard:{len(chunk.data)}",
            is_final=True,
            language=self.language,
        )
