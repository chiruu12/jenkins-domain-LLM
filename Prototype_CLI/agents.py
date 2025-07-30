import logging
from functools import lru_cache
from typing import List, Optional, Type
from pydantic import BaseModel

import config
import prompt_examples
from agno.agent import Agent
from agno.tools import Toolkit

from tools.jenkins_workspace import JenkinsWorkspaceTools
from tools.knowledge_base import KnowledgeBaseTools
from tools.log_access import LogAccessTools
from models.Openrouter.client import get_openrouter_client

from data_models import (
    CritiqueReport, DiagnosisReport, RoutingDecision
)

logger = logging.getLogger(__name__)


@lru_cache(maxsize=12)
def _load_prompt_template(prompt_path: str, example: str) -> str:
    full_path = config.PROMPTS_DIR / f"{prompt_path}.md"
    if not full_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {full_path}")

    template = full_path.read_text()
    return template.format(example_json=example)


def _create_agent(
        prompt_path: str,
        description: str,
        response_model: Type[BaseModel],
        example: str,
        base_tools: List[Toolkit],
        custom_tools: Optional[List[Toolkit]] = None,
        model_id: Optional[str] = None,
) -> Agent:
    effective_model_id = model_id or config.DEFAULT_MODEL_ID
    model_instance = get_openrouter_client(model_id=effective_model_id)
    final_tools = base_tools + (custom_tools or [])
    formatted_prompt = _load_prompt_template(prompt_path, example)

    return Agent(
        model=model_instance,
        response_model=response_model,
        tools=final_tools,
        instructions=[formatted_prompt],
        description=description,
    )


def get_common_tools(kb_tool: KnowledgeBaseTools) -> List[Toolkit]:
    workspace_tool = JenkinsWorkspaceTools(base_directory_path=str(config.WORKSPACE_BASE_DIR))
    log_tool = LogAccessTools()
    return [workspace_tool, kb_tool, log_tool]


def get_router_agent(model_id: Optional[str] = None) -> Agent:
    return _create_agent(
        prompt_path="router",
        description="Classifies the Jenkins failure type.",
        response_model=RoutingDecision,
        example=prompt_examples.ROUTING_EXAMPLE,
        base_tools=[],
        model_id=model_id
    )


def get_specialist_agent(
        agent_type: str,
        common_tools: List[Toolkit],
        model_id: Optional[str] = None
) -> Agent:
    prompt_map = {
        "CONFIGURATION_ERROR": "config_error",
        "TEST_FAILURE": "test_failure",
        "DEPENDENCY_ERROR": "dependency_error",
        "INFRA_FAILURE": "infra_failure",
        "UNKNOWN": "default",
    }
    prompt_name = prompt_map.get(agent_type, "default")

    return _create_agent(
        prompt_path=prompt_name,
        description=f"Diagnoses {agent_type} failures.",
        response_model=DiagnosisReport,
        example=prompt_examples.DIAGNOSIS_EXAMPLE,
        base_tools=common_tools,
        model_id=model_id
    )


def get_critic_agent(model_id: Optional[str] = None) -> Agent:
    return _create_agent(
        prompt_path="critic",
        description="Reviews diagnosis reports for quality and accuracy.",
        response_model=CritiqueReport,
        example=prompt_examples.CRITIQUE_EXAMPLE,
        base_tools=[LogAccessTools()],
        model_id=model_id
    )
