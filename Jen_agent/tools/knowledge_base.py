import logging
from typing import Callable, Awaitable, Optional, List
from pathlib import Path
import numpy as np
from tools.base_tool import BaseTool
from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc
from lightrag.kg.shared_storage import initialize_pipeline_status

logger = logging.getLogger(__name__)


class CoreLightRAGManager:
    """
    Manages the lifecycle and configuration of the core LightRAG instance.
    This class handles the complex asynchronous initialization and provides a clean
    internal interface for storing data in and querying the vector database.
    """
    def __init__(
            self,
            working_dir: str,
            embedding_func: Callable[[List[str]], Awaitable[np.ndarray]],
            llm_func: Callable[..., Awaitable[str]],
            reranker_func: Optional[Callable[..., Awaitable[list]]] = None
    ):
        self.working_dir = Path(working_dir)
        self.embedding_func = embedding_func
        self.llm_func = llm_func
        self.reranker_func = reranker_func

        self.rag_instance: Optional[LightRAG] = None
        self.is_initialized: bool = False

    async def initialize(self):
        if self.is_initialized:
            return

        logger.info("Initializing RAG knowledge base...")
        self.working_dir.mkdir(parents=True, exist_ok=True)

        try:
            logger.debug("Determining embedding dimension...")
            test_embedding = await self.embedding_func(["test"])
            embedding_dim = test_embedding.shape[1]
            logger.debug(f"Embedding dimension is {embedding_dim}.")
        except Exception as e:
            logger.error(f"Failed to get embedding dimension: {e}", exc_info=True)
            raise ValueError("Could not determine embedding dimension from the provided function.") from e

        self.rag_instance = LightRAG(
            working_dir=str(self.working_dir),
            embedding_func=EmbeddingFunc(embedding_dim=embedding_dim, func=self.embedding_func),
            llm_model_func=self.llm_func,
            rerank_model_func=self.reranker_func if self.reranker_func else None,
            vector_storage="FaissVectorDBStorage",
        )

        await self.rag_instance.initialize_storages()
        await initialize_pipeline_status()
        self.is_initialized = True
        logger.info("RAG knowledge base initialized successfully.")

    async def store_text(self, text_content: str, document_id: Optional[str] = None):
        if not self.is_initialized or self.rag_instance is None:
            raise RuntimeError("RAG Manager is not initialized. Call initialize() first.")
        await self.rag_instance.ainsert(input=text_content, ids=document_id)

    async def query(self, query_text: str, use_rerank: bool = False) -> str:
        if not self.is_initialized or self.rag_instance is None:
            raise RuntimeError("RAG Manager is not initialized. Call initialize() first.")

        enable_rerank_flag = use_rerank and self.reranker_func is not None
        if use_rerank and self.reranker_func is None:
            logger.warning("Reranking was requested but no reranker function is configured.")

        param = QueryParam(mode="mix", top_k=3, enable_rerank=enable_rerank_flag)
        response = await self.rag_instance.aquery(query_text, param=param)
        return str(response)


class KnowledgeBaseTools(BaseTool):
    """
    A tool to query an internal knowledge base for information about Jenkins plugins,
    solutions, and general Jenkins documentation. Use this to find solutions to similar
    problems or to understand concepts mentioned in the logs.
    """
    def __init__(self, core_manager: CoreLightRAGManager):
        super().__init__(name="knowledge_base_tools")
        self.core_manager = core_manager
        self.register(self.query_knowledge_base)

    async def query_knowledge_base(self, query: str, use_reranker: bool = True) -> str:
        logger.info(f"Agent is querying the knowledge base with: '{query}'")
        try:
            return await self.core_manager.query(query, use_rerank=use_reranker)
        except Exception as e:
            logger.error(f"Error during knowledge base query: {e}", exc_info=True)
            return f"Error: An unexpected error occurred while querying the knowledge base."
