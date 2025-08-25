import os
import logging
from typing import List, Callable, Awaitable, Optional, Dict, Any
from agno.models.base import Model
from agno.models.openrouter import OpenRouter
from models.base import BaseProvider

try:
    from openai import AsyncOpenAI
except ImportError:
    raise ImportError("`openai` is not installed. Please install it using `pip install openai`")

logger = logging.getLogger(__name__)

class OpenRouterProvider(BaseProvider):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OpenRouterProvider requires an API key.")

        self.async_client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key
        )
        logger.info("Initialized OpenRouter client.")

    def get_chat_model(self, model_id: Optional[str] = "openai/gpt-5-mini") -> Model:
        #TODO: Add a PR in Agno's repo! As they only accept the sync client for openailike class whereas in openai's
        # repo they accept both async and sync I have already contacted the maintainers of the repo regarding this issue.
        return OpenRouter(id=model_id, api_key=self.api_key, http_client=self.async_client)

    def get_embedding_function(
        self,
        **kwargs
    ) -> Callable[[List[str]], Awaitable[Any]]:
        raise NotImplementedError("OpenRouter does not provide an embedding function.")

    def get_llm_model_func(self, model_id: Optional[str] = "openai/gpt-5-mini") -> Callable[..., Awaitable[str]]:
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

    def get_reranker_model(self) -> None:
        raise NotImplementedError("Reranker models are not sourced from OpenRouter in this agent.")


