import os
import logging
from typing import List, Callable, Awaitable, Optional, Dict, Any
import numpy as np
from agno.models.base import Model
from models.base import BaseProvider

try:
    from agno.models.google import Gemini
    from google import genai
    from google.genai import Client as GeminiClient
    from google.genai.types import EmbedContentConfig,GenerateContentConfig
except ImportError:
    raise ImportError("`google-genai` not installed. Please install it using `pip install google-genai`")

logger = logging.getLogger(__name__)

class GoogleProvider(BaseProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        vertexai: bool = False
    ):
        self.vertexai = vertexai

        if self.vertexai:
            self.project_id = project_id or os.environ.get("GOOGLE_PROJECT_ID")
            self.location = location or os.environ.get("GOOGLE_PROJECT_LOCATION")
            if not all([self.project_id, self.location]):
                raise ValueError("For Vertex AI, project_id and location are required.")
            self.api_key = None
        else:
            self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
            if not self.api_key:
                raise ValueError("For PaLM Gemini API, an API key is required.")
            self.project_id = None
            self.location = None

        self.client: GeminiClient = genai.Client(
            api_key=self.api_key,
            vertexai=self.vertexai,
            project=self.project_id,
            location=self.location
        )
        if vertexai:
            logger.info(
                f"Initialized Google client for Vertex AI with project_id: {self.project_id} and location: {self.location}"
            )
        else:
            logger.info("Initialized Google client for PaLM Gemini API")

    def get_chat_model(self, model_id: Optional[str] = "gemini-2.5-flash") -> Model:
        return Gemini(
            id=model_id,
            api_key=self.api_key,
            client=self.client,
            project_id=self.project_id,
            location=self.location,
            vertexai=self.vertexai,
        )

    def get_embedding_function(
        self,
        model_id: Optional[str] = "text-embedding-004",
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> Callable[[List[str]], Awaitable[np.ndarray]]:
        logger.info(f"Creating Google embedding function for model: {model_id}")

        async def embed_texts(texts: List[str]) -> np.ndarray:
            response = await self.client.aio.models.embed_content(
                model=model_id,
                contents=texts,
                config=EmbedContentConfig(task_type=task_type),
            )
            embeddings = [embedding.values for embedding in response.embeddings]
            return np.array(embeddings)

        return embed_texts

    def get_llm_model_func(self, model_id: Optional[str] = "gemini-2.5-flash") -> Callable[..., Awaitable[str]]:
        async def llm_model_func(
            prompt: str,
            system_prompt: Optional[str] = None,
            history_messages: Optional[List[Dict[str, Any]]] = None,
            **kwargs
        ) -> str:
            if history_messages is None:
                history_messages = []

            combined_prompt = ""
            if system_prompt:
                combined_prompt += f"{system_prompt}\n"
            for msg in history_messages:
                combined_prompt += f"{msg.get('role', 'user')}: {msg.get('content', '')}\n"
            combined_prompt += f"user: {prompt}"

            response = await self.client.aio.models.generate_content(
                model=model_id,
                contents=[combined_prompt],
                config=GenerateContentConfig(max_output_tokens=500, temperature=0.1),
            )

            return response.text

        return llm_model_func

    def get_reranker_model(self) -> None:
        raise NotImplementedError("Reranker models are not sourced from Google in this agent.")
