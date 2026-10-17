"""Abstract interfaces for speech, language model, and synthesis providers.

These interfaces decouple the LiveKit agent worker pipeline from concrete vendor SDKs
(e.g., Deepgram, Cartesia, OpenAI, ElevenLabs) per ADR 1 and Section 7 of docs/ARCHITECTURE.md.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from pydantic import BaseModel, Field


class AudioChunk(BaseModel):
    """Raw audio chunk received from the caller or room audio track."""

    data: bytes = Field(description="Raw audio frame bytes")
    sample_rate: int = Field(default=16000, description="Audio sample rate in Hz")
    channels: int = Field(default=1, description="Number of audio channels")


class TranscriptionResult(BaseModel):
    """Transcript produced by an STT provider for an audio segment."""

    text: str = Field(description="Transcribed text content")
    is_final: bool = Field(default=True, description="Whether this hypothesis is final")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    language: str = Field(default="en", description="Detected or configured BCP-47 language tag")


class LLMResponseChunk(BaseModel):
    """Incremental streaming token or tool call produced by an LLM provider."""

    content: str = Field(default="", description="Incremental text token delta")
    is_final: bool = Field(default=False, description="Whether the generation stream is complete")
    tool_calls: list[dict[str, object]] | None = Field(
        default=None,
        description="Structured tool invocations requested by the model",
    )


class SynthesizedAudio(BaseModel):
    """Synthesized speech output ready for playback into a WebRTC audio track."""

    data: bytes = Field(description="Encoded or raw audio bytes")
    format: str = Field(default="pcm", description="Audio format (e.g. pcm, mp3, ogg)")
    sample_rate: int = Field(default=24000, description="Output sample rate in Hz")
    duration_ms: int = Field(default=0, ge=0, description="Audio duration in milliseconds")


class STTProvider(ABC):
    """Abstract interface for Speech-to-Text streaming and chunk transcription."""

    @abstractmethod
    def transcribe_stream(
        self, audio_stream: AsyncIterator[AudioChunk]
    ) -> AsyncIterator[TranscriptionResult]:
        """Stream continuous audio chunks and yield real-time transcription results."""

    @abstractmethod
    async def transcribe_chunk(self, chunk: AudioChunk) -> TranscriptionResult:
        """Transcribe a discrete audio segment synchronously or as a one-shot request."""


class LLMProvider(ABC):
    """Abstract interface for Large Language Model streaming and tool generation."""

    @abstractmethod
    def generate_stream(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, object]] | None = None,
    ) -> AsyncIterator[LLMResponseChunk]:
        """Stream response tokens and tool calls given a conversation history and tool schemas."""


class TTSProvider(ABC):
    """Abstract interface for Text-to-Speech synthesis and audio streaming."""

    @abstractmethod
    def synthesize_stream(self, text_stream: AsyncIterator[str]) -> AsyncIterator[bytes]:
        """Stream synthesized audio bytes from an incoming stream of text tokens."""

    @abstractmethod
    async def synthesize(self, text: str) -> SynthesizedAudio:
        """Synthesize a complete text utterance into a playable audio buffer."""
