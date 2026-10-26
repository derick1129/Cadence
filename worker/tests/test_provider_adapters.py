"""Tests for concrete worker provider adapters and provider factory."""

import pytest

from worker.agent.entrypoint import RuntimeConfig
from worker.providers.factory import ProviderFactory
from worker.providers.interfaces import AudioChunk


@pytest.mark.asyncio
async def test_provider_factory_resolution() -> None:
    """Verify factory resolves Deepgram STT, OpenAI LLM, and Cartesia TTS adapters."""
    config = RuntimeConfig(
        session_id="sess-mock",
        agent_id="agent-mock",
        agent_version_id="ver-mock",
        system_prompt="Test prompt",
        stt_config={"provider": "deepgram", "model": "nova-2"},
        llm_config={"provider": "openai", "model": "gpt-4o-mini"},
        tts_config={"provider": "cartesia", "model": "sonic-english", "voice": "default-voice"},
    )

    stt, llm, tts = ProviderFactory.create_providers(config)
    assert stt.__class__.__name__ == "DeepgramSTTProvider"
    assert llm.__class__.__name__ == "OpenAILLMProvider"
    assert tts.__class__.__name__ == "CartesiaTTSProvider"

    # Verify adapter interface contract
    stt_res = await stt.transcribe_chunk(AudioChunk(data=b"\x00\x01\x02"))
    assert stt_res.text != ""

    tokens: list[str] = []
    async for chunk in llm.generate_stream([{"role": "user", "content": "Hello"}]):
        tokens.append(chunk.content)
    assert len(tokens) > 0

    audio = await tts.synthesize("Hello world")
    assert len(audio.data) > 0
