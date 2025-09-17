import os
import logging
from typing import List, Callable, Awaitable, Optional, Any, Dict
import numpy as np
from cohere import AsyncClientV2,UserChatMessageV2
from agno.models.base import Model
from agno.models.cohere import Cohere
from models.base import BaseProvider
from lightrag.rerank import cohere_rerank
logger = logging.getLogger(__name__)

class CohereProvider(BaseProvider):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("COHERE_API_KEY")
        if not self.api_key:
            raise ValueError("For Cohere, an API key is required. Set it in your environment as COHERE_API_KEY.")

        self.client = AsyncClientV2(self.api_key)
        logger.info("Initialized Cohere client.")

    def get_chat_model(self, model_id: Optional[str] = "command-r") -> Model:
        return Cohere(
            id=model_id,
            api_key=self.api_key,
            async_client=self.client,
        )

    def get_embedding_function(
        self,
        model_id: Optional[str] = "embed-english-v3.0",
        task_type: Optional[str] = "search_document",
    ) -> Callable[[List[str]], Awaitable[np.ndarray]]:
        logger.info(f"Creating Cohere embedding function for model: {model_id}")

        async def embed_texts(texts: List[str]) -> np.ndarray:
            response = await self.client.embed(
                texts=texts,
                model=model_id,
                input_type=task_type,
                embedding_types=["float"]
            )
            return np.array(response.embeddings)

        return embed_texts

    def get_llm_model_func(self, model_id: Optional[str] = "command-r") -> Callable[..., Awaitable[str]]:
        async def llm_model_func(
            prompt: str,
            **kwargs
        ) -> str:
            response = await self.client.chat(
                model=model_id,
                messages=[UserChatMessageV2(content=prompt)],
                temperature=0.1
            )
            return response.text

        return llm_model_func

    def get_reranker_model(self, model_id: Optional[str] = "rerank-english-v3.0") -> Callable[..., Awaitable[list]]:
        logger.info(f"Creating Cohere reranker function for model: {model_id} using lightrag utility.")

        async def rerank_func_wrapper(query: str, documents: List[Dict[Any,str]], **kwargs) -> List[Dict[Any,str]]:
            reranked_results = await cohere_rerank(
                query=query,
                documents=documents,
                model=model_id,
                api_key=self.api_key,
                top_n=kwargs.get("top_n")
            )
            return reranked_results

        return rerank_func_wrapper
