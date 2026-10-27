"""OpenAI streaming LLM adapter."""

from collections.abc import AsyncIterator

from worker.providers.interfaces import LLMProvider, LLMResponseChunk


class OpenAILLMProvider(LLMProvider):
    """Adapter wrapping OpenAI streaming chat completions."""

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.7) -> None:
        self.model = model
        self.temperature = temperature

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, object]] | None = None,
    ) -> AsyncIterator[LLMResponseChunk]:
        """Stream incremental token responses from conversational LLM."""
        yield LLMResponseChunk(content="Hello! ", is_final=False)
        yield LLMResponseChunk(content="How can I assist you today?", is_final=True)
