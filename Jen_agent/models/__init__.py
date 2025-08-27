import os
import importlib
from typing import Dict
from models.base import BaseProvider
from settings import settings

_provider_cache: Dict[str, BaseProvider] = {}

def create_provider(provider_name: str) -> BaseProvider:
    if provider_name in _provider_cache:
        return _provider_cache[provider_name]

    provider_config = settings.providers.get(provider_name)
    if not provider_config:
        raise ValueError(f"Provider '{provider_name}' is not configured in config.yaml.")

    class_name = None
    module_path = None
    try:
        module_path = provider_config.module
        class_name = provider_config.class_name

        provider_module = importlib.import_module(module_path)
        ProviderClass = getattr(provider_module, class_name)

    except (ImportError, AttributeError) as e:
        raise ImportError(
            f"Could not import class '{class_name}' from module '{module_path}'. "
            f"Please check your config.yaml. Error: {e}"
        )

    init_args = {}
    for arg_name, env_var_name in provider_config.init_args.items():
        init_args[arg_name] = os.getenv(env_var_name)

    provider_instance = ProviderClass(**init_args)
    _provider_cache[provider_name] = provider_instance

    return provider_instance
