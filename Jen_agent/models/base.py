from abc import ABC, abstractmethod
from typing import List, Callable, Awaitable, Optional
import numpy as np
from agno.models.base import Model

class BaseProvider(ABC):
    @abstractmethod
    def get_chat_model(self, model_id: Optional[str]) -> Model:
        pass

    @abstractmethod
    def get_embedding_function(
        self,
        model_id: Optional[str],
        task_type: Optional[str],
    ) -> Callable[[List[str]], Awaitable[np.ndarray]]:
        pass

    @abstractmethod
    def get_llm_model_func(self, model_id: Optional[str]) -> Callable[..., Awaitable[str]]:
        pass

    @abstractmethod
    def get_reranker_model(self,model_id: Optional[str] ) -> None:
        pass
