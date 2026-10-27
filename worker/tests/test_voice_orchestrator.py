"""Tests for voice pipeline orchestrator."""

import asyncio

import pytest

from worker.agent.entrypoint import RuntimeConfig
from worker.agent.pipeline import VoicePipeline
from worker.providers.factory import ProviderFactory


@pytest.mark.asyncio
async def test_voice_orchestrator_turn_flow() -> None:
    """Verify voice orchestrator executes greetings and turn streaming."""
    config = RuntimeConfig(
        session_id="sess-orch-test",
        agent_id="agent-orch-test",
        agent_version_id="ver-orch",
        system_prompt="Be concise and friendly.",
        greeting="Hi there, how can I help you?",
        silence_timeout_s=5.0,
    )
    stt, llm, tts = ProviderFactory.create_providers(config)
    pipeline = VoicePipeline(config=config, stt=stt, llm=llm, tts=tts)

    # Greeting test
    greeting_audio = await pipeline.get_greeting_audio()
    assert greeting_audio is not None
    assert greeting_audio.data == b"Hi there, how can I help you?"

    # Conversation turn test
    chunks: list[bytes] = []
    async for chunk in pipeline.process_caller_speech("Tell me about Cadence"):
        chunks.append(chunk)

    assert len(chunks) > 0
    full_audio = b"".join(chunks).decode("utf-8")
    assert "Hello!" in full_audio


@pytest.mark.asyncio
async def test_voice_orchestrator_barge_in() -> None:
    """Verify voice orchestrator supports barge-in interruption."""
    config = RuntimeConfig(
        session_id="sess-orch-barge",
        agent_id="agent-orch-barge",
        agent_version_id="ver-orch",
        system_prompt="Prompt.",
    )
    stt, llm, tts = ProviderFactory.create_providers(config)
    pipeline = VoicePipeline(config=config, stt=stt, llm=llm, tts=tts)

    task = asyncio.create_task(pipeline.synthesize_speech("Speaking a long audio buffer..."))
    await asyncio.sleep(0.01)

    pipeline.interrupt()
    assert pipeline.is_interrupted() is True
    await task
