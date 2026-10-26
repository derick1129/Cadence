"""Voice pipeline orchestrating streaming turns, greeting, and barge-in."""

import asyncio
from collections.abc import AsyncIterator

from worker.agent.entrypoint import RuntimeConfig
from worker.providers.interfaces import LLMProvider, STTProvider, SynthesizedAudio, TTSProvider


class VoicePipeline:
    """Manages audio conversation turns between caller audio stream and providers."""

    def __init__(
        self,
        config: RuntimeConfig,
        stt: STTProvider,
        llm: LLMProvider,
        tts: TTSProvider,
    ) -> None:
        self.config = config
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self._interrupted = False
        self._chat_history: list[dict[str, str]] = [
            {"role": "system", "content": config.system_prompt}
        ]

    async def get_greeting_audio(self) -> SynthesizedAudio | None:
        """Synthesize initial greeting speech if configured."""
        if not self.config.greeting:
            return None
        return await self.tts.synthesize(self.config.greeting)

    def interrupt(self) -> None:
        """Handle caller barge-in: signal immediate cancellation of in-flight response."""
        self._interrupted = True

    def is_interrupted(self) -> bool:
        """Return True if the current generation was cancelled by caller barge-in."""
        return self._interrupted

    async def synthesize_speech(self, text: str) -> bytes:
        """Synthesize text speech while checking for barge-in cancellation."""
        if self._interrupted:
            return b""
        await asyncio.sleep(0.02)
        if self._interrupted:
            return b""
        audio = await self.tts.synthesize(text)
        return audio.data

    async def process_caller_speech(self, caller_text: str) -> AsyncIterator[bytes]:
        """Execute a full turn: append to history, stream LLM generation, and stream TTS audio."""
        self._interrupted = False
        self._chat_history.append({"role": "user", "content": caller_text})

        async def _text_token_generator() -> AsyncIterator[str]:
            async for chunk in self.llm.generate_stream(self._chat_history):
                if self._interrupted:
                    break
                if chunk.content:
                    yield chunk.content

        full_agent_response: list[str] = []
        async for audio_chunk in self.tts.synthesize_stream(_text_token_generator()):
            if self._interrupted:
                break
            full_agent_response.append(audio_chunk.decode("utf-8", errors="ignore"))
            yield audio_chunk

        # Record agent turn in history
        if full_agent_response:
            self._chat_history.append(
                {"role": "assistant", "content": "".join(full_agent_response)}
            )
