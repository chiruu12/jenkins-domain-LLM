import os
import logging
from functools import lru_cache
from agno.models.openrouter import OpenRouter

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def get_openrouter_client(model_id: str, api_key :str = os.getenv("OPENROUTER_API_KEY")) -> OpenRouter:
    """Creates and caches an OpenRouter model client."""

    if not api_key:
        logger.error("OPENROUTER_API_KEY is not set in the environment.")
        raise ValueError("OPENROUTER_API_KEY must be configured.")

    logger.info(f"Creating OpenRouter client for model: {model_id}")
    return OpenRouter(id=model_id, api_key=api_key)

