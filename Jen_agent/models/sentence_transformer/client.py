import logging
from typing import List, Callable, Awaitable, Optional
import numpy as np
import asyncio
from sentence_transformers import SentenceTransformer
from agno.models.base import Model
from models.base import BaseProvider

logger = logging.getLogger(__name__)


class SentenceTransformerProvider(BaseProvider):
    """
    A provider that uses the local sentence-transformers library for embeddings.
    This is intended as a default, local option for the conversation memory.
    """

    def __init__(self):
        logger.info("Initialized SentenceTransformerProvider (model will be loaded on first use).")

    def get_chat_model(self, model_id: Optional[str] = None) -> Model:
        raise NotImplementedError("SentenceTransformerProvider does not provide chat models.")

    def get_embedding_function(
            self,
            model_id: Optional[str] = "all-MiniLM-L6-v2",
            task_type: Optional[str] = None,
    ) -> Callable[[List[str]], Awaitable[np.ndarray]]:
        logger.info(f"Creating SentenceTransformer embedding function for model: {model_id}")


        model = SentenceTransformer(model_id)

        async def embed_texts(texts: List[str]) -> np.ndarray:
            loop = asyncio.get_running_loop()
            embeddings = await loop.run_in_executor(
                None,
                lambda: model.encode(texts, convert_to_numpy=True),
            )
            return np.array(embeddings)

        return embed_texts

    def get_llm_model_func(self, model_id: Optional[str] = None) -> Callable[..., Awaitable[str]]:
        raise NotImplementedError("SentenceTransformerProvider does not provide LLM functions.")

    def get_reranker_model(self, model_id: Optional[str] = None) -> None:
        raise NotImplementedError("SentenceTransformerProvider does not provide reranker models.")
