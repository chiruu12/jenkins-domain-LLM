import logging
import os
from typing import Optional, List, Dict, Any
import numpy as np
import asyncio
from pathlib import Path
from .base_tool import BaseTool
from pydantic import BaseModel, Field, DirectoryPath
from openai import AsyncOpenAI
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc
from lightrag.kg.shared_storage import initialize_pipeline_status
from lightrag.rerank import cohere_rerank
LIGHTRAG_AVAILABLE = True

load_dotenv()

logger = logging.getLogger(__name__)

class LightRAGConfig(BaseModel):
    working_dir: DirectoryPath = Field(default="./lightrag_workspace")
    openrouter_api_key: str = Field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY"))
    cohere_api_key: str = Field(default_factory=lambda: os.getenv("COHERE_API_KEY"))
    llm_model_id: str = Field(default="openai/gpt-4o-mini")
    embedding_model_id: str = Field(default="all-MiniLM-L6-v2")
    reranker_model_id: str = Field(default="rerank-english-v3.0")
    default_top_k: int = Field(default=3)

    class Config:
        env_file = '.env'
        extra = 'ignore'

class CoreLightRAGManager:
    def __init__(self, config: Optional[LightRAGConfig] = None):
        self.config = config or LightRAGConfig()
        self.rag_instance: Optional[LightRAG] = None
        self.is_initialized: bool = False

        if not LIGHTRAG_AVAILABLE:
            raise ImportError("Required libraries for LightRAG are not installed.")

        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        if not openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY not found.")

        cohere_api_key = os.getenv("COHERE_API_KEY")
        if not cohere_api_key:
            raise ValueError("COHERE_API_KEY not found.")

        sentence_transformer_model = SentenceTransformer(self.config.embedding_model_id)
        embedding_dimension = sentence_transformer_model.get_sentence_embedding_dimension()

        async def embedding_func(texts: List[str]) -> np.ndarray:
            return await asyncio.to_thread(sentence_transformer_model.encode, texts, convert_to_numpy=True)

        async_openai_client = AsyncOpenAI(
            api_key=openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )

        async def llm_func(prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:

            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]

            response = await async_openai_client.chat.completions.create(
                model=self.config.llm_model_id,
                messages=messages,
            )
            return response.choices[0].message.content or ""

        async def my_rerank_func(query: str, documents: list, top_n: int = None, **kwargs):
            return await cohere_rerank(
                query=query,
                documents=documents,
                model=self.config.reranker_model_id,
                api_key=self.config.cohere_api_key,
                top_n=top_n or 10
            )

        self.rag_instance = LightRAG(
            working_dir = str(self.config.working_dir),
            embedding_func = EmbeddingFunc(embedding_dim=embedding_dimension, func=embedding_func, max_token_size=512),
            llm_model_func = llm_func,
            vector_storage = "FaissVectorDBStorage",
            rerank_model_func=my_rerank_func,
        )

    async def initialize(self):
        if self.is_initialized or not self.rag_instance: return
        try:
            await self.rag_instance.initialize_storages()
            if LIGHTRAG_AVAILABLE:
                await initialize_pipeline_status()
            self.is_initialized = True
        except Exception as e:
            logger.exception(f"Exception during LightRAG initialization: {e}")
            self.is_initialized = False

    async def finalize(self):
        if not self.is_initialized or not self.rag_instance: return
        await self.rag_instance.finalize_storages()
        self.is_initialized = False

    async def store_text(self, text_content: str, document_id: Optional[str] = None):
        if not self.is_initialized or not self.rag_instance:
            raise RuntimeError("CoreLightRAGManager is not initialized.")
        await self.rag_instance.ainsert(input=text_content, ids=document_id)

    async def query(self, query_text: str) -> str:
        if not self.is_initialized or not self.rag_instance:
            raise RuntimeError("CoreLightRAGManager is not initialized.")
        param = QueryParam(mode="mix", top_k=self.config.default_top_k)
        response = await self.rag_instance.aquery(query_text, param=param)
        return response if isinstance(response, str) else str(response)


class KnowledgeBaseTools(BaseTool):
    def __init__(self, core_manager: Optional[CoreLightRAGManager] = None, prompt_dir: Optional[str] = "prompts"):
        super().__init__(name="knowledge_base_tools", prompt_dir=Path(prompt_dir).resolve())
        self.core_manager = core_manager

        if LIGHTRAG_AVAILABLE and self.core_manager and self.core_manager.rag_instance:
            self.register(self.query_knowledge_base)
        else:
            self.register(self.dummy_query)

    async def query_knowledge_base(self, query: str) -> str:
        if not self.core_manager or not self.core_manager.is_initialized:
            return "Error: Knowledge Base tool is not available or initialized."
        try:
            return await self.core_manager.query(query)
        except Exception as e:
            logger.exception(f"Error during knowledge base query: {e}")
            return f"Error during knowledge base query: {e}"

    def dummy_query(self, query: str) -> str:
        logger.warning(f"Knowledge Base tool is not configured or available agent's query was: {query}.")
        return "Knowledge Base is not configured or available."

