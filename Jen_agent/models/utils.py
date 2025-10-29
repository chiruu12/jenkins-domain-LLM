import importlib
from typing import List, Tuple
from settings import settings


def get_provider_capabilities() -> Tuple[List[str], List[str]]:
    """
    Dynamically inspects all configured providers to determine their
    capabilities without fully instantiating them.

    Returns:
        A tuple containing two lists: (chat_providers, reranker_providers)
    """
    chat_providers = []
    reranker_providers = []

    for name, provider_config in settings.providers.items():
        try:
            module = importlib.import_module(provider_config.module)
            provider_class = getattr(module, provider_config.class_name)

            if getattr(provider_class, 'supports_chat', False):
                chat_providers.append(name)
            if getattr(provider_class, 'supports_reranker', False):
                reranker_providers.append(name)
        except (ImportError, AttributeError) as e:
            print(f"Warning: Could not inspect provider '{name}': {e}")
            pass

    return sorted(chat_providers), sorted(reranker_providers)
