"""Factory creating provider adapters based on RuntimeConfig."""

from worker.agent.entrypoint import RuntimeConfig
from worker.providers.cartesia import CartesiaTTSProvider
from worker.providers.deepgram import DeepgramSTTProvider
from worker.providers.interfaces import LLMProvider, STTProvider, TTSProvider
from worker.providers.openai import OpenAILLMProvider


class ProviderFactory:
    """Factory resolving STT, LLM, and TTS providers according to session runtime config."""

    @staticmethod
    def create_providers(
        config: RuntimeConfig,
    ) -> tuple[STTProvider, LLMProvider, TTSProvider]:
        """Instantiate concrete STT, LLM, and TTS provider adapters."""
        stt_model = str(config.stt_config.get("model", "nova-2"))
        stt = DeepgramSTTProvider(model=stt_model)

        llm_model = str(config.llm_config.get("model", "gpt-4o-mini"))
        llm = OpenAILLMProvider(model=llm_model)

        tts_model = str(config.tts_config.get("model", "sonic-english"))
        voice = str(config.tts_config.get("voice", "default-voice"))
        tts = CartesiaTTSProvider(model=tts_model, voice=voice)

        return stt, llm, tts
