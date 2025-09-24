import os
import logging
from typing import List, Callable, Awaitable, Optional, Dict, Any
from agno.models.base import Model
from models.base import BaseProvider
try:
    from agno.models.groq import Groq
    from groq import AsyncGroq as AsyncGroqClient
    from groq import Groq as GroqClient
except ImportError:
    raise ImportError("`groq` is not installed. Please install it using `pip install groq`")

logger = logging.getLogger(__name__)

class GroqProvider(BaseProvider):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GroqProvider requires an API key.")

        self.async_client = AsyncGroqClient(api_key=self.api_key)
        logger.info("Initialized Groq client")


    def get_chat_model(self, model_id: Optional[str] = "openai/gpt-oss-120b") -> Model:
        return Groq(id=model_id, api_key=self.api_key,async_client=self.async_client)

    def get_llm_model_func(self, model_id: Optional[str] = "openai/gpt-oss-120b") -> Callable[..., Awaitable[str]]:

        async def llm_model_func(
            prompt: str,
            system_prompt: Optional[str] = None,
            history_messages: Optional[List[Dict[str, Any]]] = None,
            **kwargs
        ) -> str:
            if history_messages is None:
                history_messages = []

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.extend(history_messages)
            messages.append({"role": "user", "content": prompt})

            response = await self.async_client.chat.completions.create(
                model=model_id,
                messages=messages,
                **kwargs
            )
            return response.choices[0].message.content

        return llm_model_func

    def get_embedding_function(self, **kwargs) -> None:
        raise NotImplementedError("Groq does not provide embedding models.")

    def get_reranker_model(self, **kwargs) -> None:
        raise NotImplementedError("Groq does not provide reranker models.")

    async def close(self):
        """Gracefully closes the underlying asynchronous HTTP client."""
        if self.async_client:
            await self.async_client.close()
