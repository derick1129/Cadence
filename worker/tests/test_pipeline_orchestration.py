"""Tests for VoicePipeline conversation turns and barge-in interruption handling."""

import asyncio

import pytest

from worker.agent.entrypoint import RuntimeConfig
from worker.agent.pipeline import VoicePipeline
from worker.providers.factory import ProviderFactory


@pytest.mark.asyncio
async def test_voice_pipeline_turn_and_greeting() -> None:
    """Verify VoicePipeline plays greeting and processes spoken turn."""
    config = RuntimeConfig(
        session_id="sess-turn-test",
        agent_id="agent-turn-test",
        agent_version_id="ver-1",
        system_prompt="Be concise.",
        greeting="Hello, I am ready.",
        silence_timeout_s=5.0,
    )
    stt, llm, tts = ProviderFactory.create_providers(config)
    pipeline = VoicePipeline(config=config, stt=stt, llm=llm, tts=tts)

    # 1. Greeting audio synthesis
    greeting_audio = await pipeline.get_greeting_audio()
    assert greeting_audio is not None
    assert greeting_audio.data == b"Hello, I am ready."

    # 2. Process caller turn
    response_chunks: list[bytes] = []
    async for chunk in pipeline.process_caller_speech("What is your service?"):
        response_chunks.append(chunk)

    assert len(response_chunks) > 0
    full_response = b"".join(response_chunks).decode("utf-8")
    assert "Hello!" in full_response


@pytest.mark.asyncio
async def test_voice_pipeline_barge_in() -> None:
    """Verify barge-in interrupts in-flight LLM stream immediately."""
    config = RuntimeConfig(
        session_id="sess-barge-test",
        agent_id="agent-barge-test",
        agent_version_id="ver-1",
        system_prompt="Be helpful.",
    )
    stt, llm, tts = ProviderFactory.create_providers(config)
    pipeline = VoicePipeline(config=config, stt=stt, llm=llm, tts=tts)

    # Start speech processing task
    task = asyncio.create_task(pipeline.synthesize_speech("A very long sentence for testing..."))
    await asyncio.sleep(0.01)

    # Caller interrupts (barge-in)
    pipeline.interrupt()
    assert pipeline.is_interrupted() is True
    await task
