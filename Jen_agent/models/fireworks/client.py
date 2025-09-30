import os
import logging
from typing import List, Callable, Awaitable, Optional, Any, Dict
import numpy as np
from openai import AsyncOpenAI
from agno.models.base import Model
from agno.models.fireworks import Fireworks
from models.base import BaseProvider

logger = logging.getLogger(__name__)

class FireworksProvider(BaseProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.fireworks.ai/inference/v1"):
        self.api_key = api_key or os.environ.get("FIREWORKS_API_KEY")
        if not self.api_key:
            raise ValueError("For Fireworks AI, an API key is required. Set it in your environment as FIREWORKS_API_KEY.")
        self.base_url = base_url
        logger.info(f"Initialized Fireworks client for base_url: {self.base_url}")

    def get_chat_model(self, model_id: Optional[str] = "accounts/fireworks/models/firefunction-v2") -> Model:
        logger.info(f"Getting chat model for model_id: {model_id} and base_url: {self.base_url}")
        return Fireworks(
            id=model_id,
            api_key=self.api_key,
        )

    def get_embedding_function(
            self,
            model_id: Optional[str] = "nomic-ai/nomic-embed-text-v1.5",
            task_type: Optional[str] = "search_document",
    ) -> Callable[[List[str]], Awaitable[np.ndarray]]:
        logger.info(f"Creating Fireworks embedding function for model: {model_id}")

        async def embed_texts(texts: List[str]) -> np.ndarray:
            client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

            if task_type:
                    prefixed_texts = [f"{task_type}: {text}" for text in texts]
            else:
                prefixed_texts = texts

            response = await client.embeddings.create(
                model=model_id,
                input=prefixed_texts
            )

            embeddings = [embedding.embedding for embedding in response.data]
            return np.array(embeddings)

        return embed_texts

    def get_llm_model_func(self, model_id: Optional[str] = "accounts/fireworks/models/llama-v3p3-70b-instruct") -> Callable[..., Awaitable[str]]:
        async def llm_model_func(
            prompt: str,
            system_prompt: Optional[str] = None,
            history_messages: Optional[List[Dict[str, Any]]] = None,
            **kwargs
        ) -> str:
            client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if history_messages:
                messages.extend(history_messages)
            messages.append({"role": "user", "content": prompt})

            response = await client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=0.1,
            )
            return response.choices[0].message.content or ""

        return llm_model_func

    def get_reranker_model(self, model_id: Optional[str] = None) -> None:
        raise NotImplementedError("FireworksProvider does not provide a reranker model.")
