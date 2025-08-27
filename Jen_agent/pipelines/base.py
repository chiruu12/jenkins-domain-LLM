from abc import ABC, abstractmethod
from agno.models.base import Model

from agents import AgentFactory
from log_manager import LLMInteractionLogger
from models import create_provider
from settings import settings

class BasePipeline(ABC):
    def __init__(self, agent_factory: AgentFactory, llm_logger: LLMInteractionLogger):
        self.agent_factory = agent_factory
        self.llm_logger = llm_logger
        self.model = self._get_default_model()

    def _get_default_model(self) -> Model:
        provider = create_provider(settings.defaults.provider)
        return provider.get_chat_model(model_id=settings.defaults.chat_model)

    @abstractmethod
    async def run(self, **kwargs) -> str:
        pass
