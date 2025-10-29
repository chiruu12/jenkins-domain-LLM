from abc import ABC, abstractmethod
from typing import Any, List, Union
from agno.models.base import Model
from agents import AgentFactory
from log_manager import LLMInteractionLogger
from memory import ConversationMemoryManager
from data_models import (
    ConversationTurn,
    InitialLogInput,
    InitialInteractiveInput,
    FollowupInput,
    SessionSettings
)
import json
from typing import Dict


class BasePipeline(ABC):
    def __init__(
            self,
            agent_factory: AgentFactory,
            llm_logger: LLMInteractionLogger,
            model: Model,
            conversation_memory: ConversationMemoryManager,
            session_settings: SessionSettings,
    ):
        self.agent_factory = agent_factory
        self.llm_logger = llm_logger
        self.model = model
        self.conversation_memory = conversation_memory
        self.session_settings = session_settings
        self.session_state: Dict[str, Any] = {}

    def _construct_prompt_with_memory(
        self,
        base_prompt: str,
        short_term_history: List[ConversationTurn],
        long_term_memory: List[ConversationTurn]
    ) -> str:
        prompt_parts = []
        if short_term_history:
            history_str = "\n---\n".join([
                f"User: {turn.user_input}\nAgent: {json.dumps(turn.agent_response)}"
                for turn in short_term_history
            ])
            prompt_parts.append(f"### Recent Conversation History (Short-Term Memory)\n{history_str}")
        if long_term_memory:
            memory_str = "\n---\n".join([
                f"User: {turn.user_input}\nAgent: {json.dumps(turn.agent_response)}"
                for turn in long_term_memory
            ])
            prompt_parts.append(f"### Relevant Past Conversations (Long-Term Memory)\n{memory_str}")
        prompt_parts.append(f"### Current Task\n{base_prompt}")
        return "\n\n".join(prompt_parts)

    @abstractmethod
    async def run(self, pipeline_input: Union[InitialLogInput, InitialInteractiveInput]) -> Any:
        pass

    @abstractmethod
    async def run_followup(self, followup_input: FollowupInput) -> Any:
        pass