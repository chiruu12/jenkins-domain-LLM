import os
import logging
from typing import List, Callable, Awaitable, Optional, Dict, Any
import numpy as np
from agno.models.base import Model
from agno.models.lmstudio import LMStudio
from models.base import BaseProvider
try:
    from openai import AsyncOpenAI
except ImportError:
    raise ImportError("`openai` is not installed. Please install it using `pip install openai`")

logger = logging.getLogger(__name__)

class LMStudioProvider(BaseProvider):
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.environ.get("LMSTUDIO_BASE_URL")
        if not self.base_url:
            raise ValueError("LMStudioProvider requires a base_url (e.g., 'http://localhost:1234/').")

        self.async_client = AsyncOpenAI(base_url=self.base_url, api_key="not-needed")
        logger.info(f"Initialized LMStudio client for base_url: {self.base_url}")

    def get_chat_model(self, model_id: Optional[str] = "qwen/qwen3-4b-thinking-2507") -> Model:
        return LMStudio(id=model_id, base_url=self.base_url, http_client=self.async_client)

    def get_embedding_function(
        self,
        model_id: Optional[str] = "text-embedding-qwen3-embedding-0.6b",
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> Callable[[List[str]], Awaitable[np.ndarray]]:
        async def embed_texts(texts: List[str]) -> np.ndarray:
            response = await self.async_client.embeddings.create(input=texts, model=model_id)
            embeddings = [item.embedding for item in response.data]
            return np.array(embeddings)

        return embed_texts

    def get_llm_model_func(self, model_id: Optional[str] = "qwen/qwen3-4b-thinking-2507") -> Callable[..., Awaitable[str]]:
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
        raise NotImplementedError("Reranker models are not sourced from LMStudio in this agent.")
