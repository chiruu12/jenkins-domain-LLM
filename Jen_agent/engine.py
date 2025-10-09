import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Any, Union

from agno.models.base import Model
from agents import AgentFactory
from data_models import (
    OperatingMode, SessionSettings, InitialLogInput,
    InitialInteractiveInput, FollowupInput, ConversationTurn
)
from log_manager import LLMInteractionLogger, setup_application_logger
from memory import ConversationMemoryManager, SessionJsonLogger
from models import create_provider
from pipeline import create_pipeline
from sanitizer import ContentSanitizer, CredentialMapper
from settings import settings
from tools import KnowledgeBaseTools, JenkinsWorkspaceTools, LogAccessTools
from tools.knowledge_base import CoreLightRAGManager

os.environ["TOKENIZERS_PARALLELISM"] = "false"


class AgentEngine:
    def __init__(self, session_settings: SessionSettings):
        self.session_settings = session_settings
        self.app_dir = Path("agent_workspace")
        self.runs_dir = self.app_dir / "runs"
        self.logs_dir = self.app_dir / "logs"
        self.run_id = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        self.run_dir = self.runs_dir / self.run_id
        for d in [self.app_dir, self.runs_dir, self.logs_dir, self.run_dir]:
            d.mkdir(parents=True, exist_ok=True)
        setup_application_logger(self.logs_dir, self.run_id)
        self.session_logger = SessionJsonLogger(self.runs_dir, self.run_id)
        self.llm_logger = LLMInteractionLogger(self.logs_dir, self.run_id)
        self.conversation_memory: Optional[ConversationMemoryManager] = None
        self.sanitizer = ContentSanitizer()
        self.mapper = CredentialMapper()
        self.log_access_tools: Optional[LogAccessTools] = None
        self.jenkins_workspace_tools: Optional[JenkinsWorkspaceTools] = None
        self.knowledge_base_tools: Optional[KnowledgeBaseTools] = None
        self.agent_factory: Optional[AgentFactory] = None

    def get_active_model(self) -> Model:
        provider = create_provider(self.session_settings.provider)
        return provider.get_chat_model(model_id=self.session_settings.chat_model)

    async def initialize(self):
        if self.session_settings.use_conversation_memory:
            memory_embedding_provider = create_provider(settings.memory_settings.embedding_provider)
            memory_embedding_func = memory_embedding_provider.get_embedding_function(
                model_id=settings.memory_settings.embedding_model,
                task_type=settings.memory_settings.task_type
            )
            self.conversation_memory = ConversationMemoryManager(embedding_func=memory_embedding_func)
            await self.conversation_memory.initialize()

        rag_provider = create_provider(settings.rag_settings.llm_provider)
        rag_llm_func = rag_provider.get_llm_model_func(model_id=settings.rag_settings.llm_model)
        embedding_provider = create_provider(settings.rag_settings.embedding_provider)
        embedding_func = embedding_provider.get_embedding_function(
            model_id=settings.rag_settings.embedding_model, task_type=settings.rag_settings.task_type
        )
        reranker_func = None
        if self.session_settings.use_reranker and self.session_settings.reranker_provider:
            reranker_provider = create_provider(self.session_settings.reranker_provider)
            reranker_func = reranker_provider.get_reranker_model(model_id=self.session_settings.reranker_model)
        rag_manager = CoreLightRAGManager(
            working_dir=str(self.run_dir / "rag_workspace"),
            llm_func=rag_llm_func, embedding_func=embedding_func, reranker_func=reranker_func
        )
        await rag_manager.initialize()
        self.log_access_tools = LogAccessTools()
        self.jenkins_workspace_tools = JenkinsWorkspaceTools(str(self.run_dir), self.sanitizer, self.mapper)
        self.knowledge_base_tools = KnowledgeBaseTools(rag_manager)
        tools_dict = {
            "log_access_tools": self.log_access_tools,
            "jenkins_workspace_tools": self.jenkins_workspace_tools,
            "knowledge_base_tools": self.knowledge_base_tools
        }
        self.agent_factory = AgentFactory(configured_tools=tools_dict)

    def create_pipeline(self, mode: OperatingMode):
        active_model = self.get_active_model()
        return create_pipeline(
            mode=mode, agent_factory=self.agent_factory, llm_logger=self.llm_logger,
            model=active_model, conversation_memory=self.conversation_memory,
            session_settings=self.session_settings
        )

    async def process_turn(
            self,
            pipeline: Any,
            pipeline_input: Union[InitialLogInput, InitialInteractiveInput, FollowupInput],
            is_first_turn: bool
    ) -> Any:
        user_query = ""
        short_term_history: List[ConversationTurn] = []
        long_term_memory: List[ConversationTurn] = []

        if isinstance(pipeline_input, (InitialInteractiveInput, FollowupInput)):
            user_query = pipeline_input.user_input
        elif isinstance(pipeline_input, InitialLogInput):
            user_query = pipeline_input.raw_log
            self.log_access_tools.set_log_contents(sanitized_log=user_query, raw_log=user_query)

        if not is_first_turn and self.session_settings.use_conversation_memory and self.conversation_memory:
            short_term_history = self.conversation_memory.get_short_term_history(self.run_id)
            long_term_memory = await self.conversation_memory.retrieve_relevant_turns(user_query, self.run_id)

        pipeline_input.short_term_history = short_term_history
        pipeline_input.long_term_memory = long_term_memory

        if is_first_turn:
            result_object = await pipeline.run(pipeline_input)
        else:
            result_object = await pipeline.run_followup(pipeline_input)

        rehydrated_result = self.mapper.rehydrate_model(result_object)

        if self.session_settings.use_conversation_memory and self.conversation_memory and hasattr(rehydrated_result,
                                                                                                  'model_dump'):
            await self.conversation_memory.add_turn(self.run_id, user_query, rehydrated_result)

        return rehydrated_result

    def setup_workspace(self, workspace_path: Optional[Path]):
        if workspace_path and workspace_path.is_dir():
            shutil.copytree(workspace_path, self.run_dir, dirs_exist_ok=True)

    def close(self):
        if self.conversation_memory:
            self.conversation_memory.close()
        self.session_logger.save()