import os
import logging
from typing import List, Callable, Awaitable, Optional, Any, Dict
import numpy as np
from openai import AsyncOpenAI
from agno.models.base import Model
from agno.models.openai import OpenAIChat
from models.base import BaseProvider

logger = logging.getLogger(__name__)

class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("For OpenAI, an API key is required. Set it in your environment as OPENAI_API_KEY.")

        self.client = AsyncOpenAI(api_key=self.api_key)
        logger.info("Initialized OpenAI client.")

    def get_chat_model(self, model_id: Optional[str] = "gpt-4.1-mini") -> Model:
        return OpenAIChat(
            id=model_id,
            api_key=self.api_key,
        )

    def get_embedding_function(
        self,
        model_id: Optional[str] = "text-embedding-3-small",
        task_type: Optional[str] = None,
    ) -> Callable[[List[str]], Awaitable[np.ndarray]]:
        logger.info(f"Creating OpenAI embedding function for model: {model_id}")

        async def embed_texts(texts: List[str]) -> np.ndarray:
            response = await self.client.embeddings.create(
                input=texts,
                model=model_id
            )
            embeddings = [item.embedding for item in response.data]
            return np.array(embeddings)

        return embed_texts

    def get_llm_model_func(self, model_id: Optional[str] = "gpt-4o-mini") -> Callable[..., Awaitable[str]]:
        async def llm_model_func(
            prompt: str,
            system_prompt: Optional[str] = None,
            history_messages: Optional[List[Dict[str, Any]]] = None,
            **kwargs
        ) -> str:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if history_messages:
                messages.extend(history_messages)
            messages.append({"role": "user", "content": prompt})

            response = await self.client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=0.1,
            )
            return response.choices[0].message.content or ""

        return llm_model_func

    def get_reranker_model(self, model_id: Optional[str] = None) -> None:
        logger.warning("OpenAI does not provide a reranker model. This function will do nothing.")
        raise NotImplementedError("Reranker models are not available from OpenAI in this agent.")
