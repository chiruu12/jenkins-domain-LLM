from agno.models.cohere import Cohere
from agno.models.deepinfra import DeepInfra
from agno.models.deepseek import DeepSeek
from agno.models.fireworks import Fireworks
from agno.models.google import Gemini
from agno.models.groq import Groq
from agno.models.huggingface import HuggingFace
from agno.models.meta import Llama
from agno.models.mistral import MistralChat
from agno.models.openai import OpenAIChat
from agno.models.openrouter import OpenRouter
from agno.models.together import Together

from agno.models.vllm import vLLM
from agno.models.litellm import LiteLLM
from agno.models.lmstudio import LMStudio
from agno.models.ollama import Ollama

from pydantic import ValidationError
from data_models import ModelConfig, LLMCatalog, ProviderConfig
import logging

logger = logging.getLogger(__name__)




#TODO: Add support for additional providers and models as needed.
_providers_data = {
    "OpenAI": {"model_class": OpenAIChat, "default_model": "gpt-4o-mini"},
    "Google": {"model_class": Gemini, "default_model": "gemini-1.5-flash-latest",
               "requires_args": ["project_id", "location", "vertexai"]},
    "Cohere": {"model_class": Cohere, "default_model": "command-r"},
    "Groq": {"model_class": Groq, "default_model": "llama3-8b-8192"},
    "Fireworks": {"model_class": Fireworks, "default_model": "accounts/fireworks/models/firefunction-v2"},
    "Meta": {"model_class": Llama, "default_model": "Llama-3.1-8B-Instruct"},
    "Mistral": {"model_class": MistralChat, "default_model": "mistral-small-latest"},
    "Together": {"model_class": Together, "default_model": "meta-llama/Llama-3.1-8B-Instruct-Turbo"},
    "HuggingFace": {"model_class": HuggingFace, "default_model": "meta-llama/Meta-Llama-3-8B-Instruct"},
    "OpenRouter": {"model_class": OpenRouter, "default_model": "meta-llama/llama-3-sonar-small-32k-online"},
    "DeepInfra": {"model_class": DeepInfra, "default_model": "meta-llama/Llama-2-70b-chat-hf"},
    "DeepSeek": {"model_class": DeepSeek, "default_model": "deepseek-chat"},
    # the providers below are commented out as they will require additional setup.
    #"Ollama": {"model_class": Ollama, "default_model": "llama3", "requires_args": ["base_url"]},
    #"LMStudio": {"model_class": LMStudio, "default_model": "local-model"},
    #"LiteLLM": {"model_class": LiteLLM, "default_model": "gpt-4o"},
    #"vLLM": {"model_class": vLLM, "default_model": "meta-llama/Llama-3.1-8B-Instruct", "requires_args": ["base_url"]},
}

#TODO: Add the mappings for the providers to the catalog.

_mappings_data = {
    "OpenAI": {"GPT-4o": "gpt-4o", "GPT-4o Mini": "gpt-4o-mini", "GPT-4": "gpt-4"},
    "Google": {"Gemini 2.5 Pro": "gemini-2.5-pro", "Gemini 2.5 Flash": "gemini-2.5-flash","Gemini 2.5 Flash Lite": "gemini-2.5-flash-lite-preview-06-17"},
    "Groq": {"Llama 3.1 70B": "llama-3.1-70b-versatile", "Llama 3.1 8B": "llama-3.1-8b-versatile",
             "Mixtral 8x7B": "mixtral-8x7b-32768"},
    "Fireworks": {
        "Qwen3 235B": "accounts/fireworks/models/qwen3-235b-a22b",
        "Firefunction v2": "accounts/fireworks/models/firefunction-v2",
        "Llama 3.1 70B": "accounts/fireworks/models/llama-v3p1-70b-instruct",
        "Llama 3.1 8B": "accounts/fireworks/models/llama-v3p1-8b-instruct",
    },
    "OpenRouter": {
        "Auto": "meta-llama/llama-3-sonar-small-32k-online",
        "GPT-4o": "openai/gpt-4o",
        "Claude 3.5 Sonnet": "anthropic/claude-3.5-sonnet",
        "Llama 3.1 405B": "meta-llama/llama-3.1-405b-instruct",
    },
    # the providers below are commented out as they will require additional setup.
    #"vLLM": {"Self-Hosted Endpoint": "user-defined-vllm-model"},
    #"Ollama": {"Llama 3": "llama3", "Phi-3": "phi3", "Qwen": "qwen"},
    #"LMStudio": {"Self-Hosted Endpoint": "user-defined-lmstudio-model"},
}

try:
    CATALOG = LLMCatalog(providers=_providers_data, mappings=_mappings_data)
except ValidationError as e:
    print(f"FATAL: LLM Catalog configuration is invalid.\n{e}")
    raise


def get_model_config(provider_key: str, model_key: str) -> ModelConfig:
    provider_map = CATALOG.mappings.get(provider_key)
    if provider_map and model_key in provider_map:
        model_id = provider_map[model_key]
        return ModelConfig(provider_key=provider_key, model_key=model_key, model_id=model_id)

    logger.warning(
        f"Model key {model_key} not found for provider {provider_key}. Attempting provider's default."
    )
    provider_config = CATALOG.providers.get(provider_key)
    if provider_config:
        default_model_id = provider_config.default_model
        default_model_key = f"Default ({default_model_id.split('/')[-1]})"
        logger.info(
            f"Falling back to default model for {provider_key}: {default_model_id}",
        )
        return ModelConfig(provider_key=provider_key, model_key=default_model_key, model_id=default_model_id)

    raise ValueError(f"Error: Provider '{provider_key}' is not a valid provider. Check the CATALOG configuration.")

