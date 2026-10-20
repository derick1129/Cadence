"""Tests for provider factory resolving provider adapters."""

import pytest

from worker.agent.entrypoint import RuntimeConfig
from worker.providers.cartesia import CartesiaTTSProvider
from worker.providers.deepgram import DeepgramSTTProvider
from worker.providers.factory import ProviderFactory
from worker.providers.openai import OpenAILLMProvider


@pytest.mark.asyncio
async def test_provider_factory_resolution() -> None:
    """Verify ProviderFactory returns configured provider implementations."""
    config = RuntimeConfig(
        session_id="sess-test",
        agent_id="agent-test",
        agent_version_id="ver-test",
        system_prompt="System prompt",
        stt_config={"provider": "deepgram", "model": "nova-2"},
        llm_config={"provider": "openai", "model": "gpt-4o-mini"},
        tts_config={"provider": "cartesia", "model": "sonic-english", "voice": "default-voice"},
    )

    stt, llm, tts = ProviderFactory.create_providers(config)
    assert isinstance(stt, DeepgramSTTProvider)
    assert isinstance(llm, OpenAILLMProvider)
    assert isinstance(tts, CartesiaTTSProvider)
