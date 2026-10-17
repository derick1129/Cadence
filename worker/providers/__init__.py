"""Worker provider interfaces and data transfer models."""

from worker.providers.interfaces import (
    AudioChunk,
    LLMProvider,
    LLMResponseChunk,
    STTProvider,
    SynthesizedAudio,
    TranscriptionResult,
    TTSProvider,
)

__all__ = [
    "AudioChunk",
    "LLMProvider",
    "LLMResponseChunk",
    "STTProvider",
    "SynthesizedAudio",
    "TranscriptionResult",
    "TTSProvider",
]
