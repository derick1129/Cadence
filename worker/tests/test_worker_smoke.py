"""Unit smoke tests for worker provider interfaces and runtime configuration."""

from collections.abc import AsyncIterator

import httpx
import pytest
from pydantic import ValidationError

from worker.agent.entrypoint import (
    RuntimeConfig,
    WorkerConfig,
    create_worker_options,
    extract_session_id,
    fetch_runtime_config,
)
from worker.providers.interfaces import (
    AudioChunk,
    LLMProvider,
    LLMResponseChunk,
    STTProvider,
    SynthesizedAudio,
    TranscriptionResult,
    TTSProvider,
)


class DummySTT(STTProvider):
    """Concrete mock STT provider for contract verification."""

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[AudioChunk]
    ) -> AsyncIterator[TranscriptionResult]:
        async for chunk in audio_stream:
            yield TranscriptionResult(text=f"heard:{len(chunk.data)}", is_final=True)

    async def transcribe_chunk(self, chunk: AudioChunk) -> TranscriptionResult:
        return TranscriptionResult(text=f"heard:{len(chunk.data)}", is_final=True)


class DummyLLM(LLMProvider):
    """Concrete mock LLM provider for contract verification."""

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, object]] | None = None,
    ) -> AsyncIterator[LLMResponseChunk]:
        yield LLMResponseChunk(content="Hello", is_final=False)
        yield LLMResponseChunk(content=" world!", is_final=True)


class DummyTTS(TTSProvider):
    """Concrete mock TTS provider for contract verification."""

    async def synthesize_stream(self, text_stream: AsyncIterator[str]) -> AsyncIterator[bytes]:
        async for text in text_stream:
            yield text.encode("utf-8")

    async def synthesize(self, text: str) -> SynthesizedAudio:
        data = text.encode("utf-8")
        return SynthesizedAudio(data=data, format="pcm", sample_rate=24000, duration_ms=100)


def test_provider_interfaces_cannot_be_instantiated_directly() -> None:
    """Ensure ABCs prevent instantiation without implementing abstract methods."""
    with pytest.raises(TypeError):
        STTProvider()  # type: ignore[abstract]
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore[abstract]
    with pytest.raises(TypeError):
        TTSProvider()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_concrete_providers_fulfill_contract() -> None:
    """Ensure concrete providers implement the streaming interfaces cleanly."""
    stt = DummySTT()
    llm = DummyLLM()
    tts = DummyTTS()

    stt_res = await stt.transcribe_chunk(AudioChunk(data=b"\x00\x01\x02"))
    assert stt_res.text == "heard:3"
    assert stt_res.is_final is True

    llm_tokens: list[str] = []
    async for chunk in llm.generate_stream([{"role": "user", "content": "hi"}]):
        llm_tokens.append(chunk.content)
    assert "".join(llm_tokens) == "Hello world!"

    tts_res = await tts.synthesize("test speech")
    assert tts_res.data == b"test speech"
    assert tts_res.sample_rate == 24000


def test_provider_schemas_validation() -> None:
    """Test validation and defaults for provider data schemas."""
    chunk = AudioChunk(data=b"1234")
    assert chunk.sample_rate == 16000
    assert chunk.channels == 1

    trans = TranscriptionResult(text="hello")
    assert trans.confidence == 1.0
    assert trans.language == "en"

    with pytest.raises(ValidationError):
        TranscriptionResult(text="bad", confidence=1.5)


def test_worker_config_defaults_and_overrides() -> None:
    """Test default values and custom field overrides for WorkerConfig."""
    default_cfg = WorkerConfig()
    assert default_cfg.livekit_url == "ws://localhost:7880"
    assert default_cfg.agent_name == "cadence-voice-agent"

    custom_cfg = WorkerConfig(agent_name="custom-bot", livekit_url="wss://livekit.example.com")
    assert custom_cfg.agent_name == "custom-bot"
    assert custom_cfg.livekit_url == "wss://livekit.example.com"


def test_runtime_config_schema() -> None:
    """Test serialization and deserialization of RuntimeConfig."""
    payload = {
        "session_id": "sess_123",
        "agent_id": "agent_456",
        "agent_version_id": "ver_789",
        "system_prompt": "You are a helpful assistant.",
        "greeting": "Hello!",
        "stt_config": {"model": "nova-2"},
        "llm_config": {"model": "gpt-4o-mini"},
        "tts_config": {"voice": "sonic-english"},
        "silence_timeout_s": 8.0,
        "max_duration_s": 1800,
    }
    config = RuntimeConfig.model_validate(payload)
    assert config.session_id == "sess_123"
    assert config.greeting == "Hello!"
    assert config.silence_timeout_s == 8.0


def test_extract_session_id() -> None:
    """Ensure extract_session_id prefers metadata over room name."""
    assert extract_session_id("room-abc", "sess-custom-123") == "sess-custom-123"
    assert extract_session_id("room-abc", None) == "room-abc"
    assert extract_session_id("room-abc", "   ") == "room-abc"


def test_create_worker_options() -> None:
    """Ensure create_worker_options instantiates valid WorkerOptions."""
    cfg = WorkerConfig(agent_name="test-worker", livekit_url="wss://test.livekit.io")
    options = create_worker_options(config=cfg)
    assert options.agent_name == "test-worker"
    assert options.ws_url == "wss://test.livekit.io"
    assert callable(options.entrypoint_fnc)


@pytest.mark.asyncio
async def test_fetch_runtime_config_success() -> None:
    """Verify runtime config retrieval with internal service authentication header."""
    expected_payload = {
        "session_id": "sess_abc",
        "agent_id": "agent_001",
        "agent_version_id": "ver_001",
        "system_prompt": "Answer caller questions politely.",
        "greeting": "Welcome to Cadence.",
        "silence_timeout_s": 10.0,
        "max_duration_s": 3600,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-Internal-Service-Token") == "secret-token"
        assert request.url.path == "/internal/sessions/sess_abc/runtime-config"
        return httpx.Response(status_code=200, json=expected_payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        cfg = WorkerConfig(
            backend_internal_url="http://localhost:8000/internal",
            internal_service_token="secret-token",
        )
        runtime_config = await fetch_runtime_config("sess_abc", cfg, client=client)

    assert runtime_config.session_id == "sess_abc"
    assert runtime_config.greeting == "Welcome to Cadence."


@pytest.mark.asyncio
async def test_fetch_runtime_config_error_status() -> None:
    """Verify HTTPStatusError is raised if backend returns error status."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=404, json={"detail": "Session not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        cfg = WorkerConfig()
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_runtime_config("nonexistent", cfg, client=client)
