import logging
from functools import lru_cache
from typing import List, Optional, Type
from pydantic import BaseModel

import config
import prompt_examples
from agno.agent import Agent
from tools.base_tool import BaseTool

from tools.jenkins_workspace import JenkinsWorkspaceTools
from tools.knowledge_base import KnowledgeBaseTools
from tools.log_access import LogAccessTools
from models.Openrouter.client import get_openrouter_client

from data_models import (
    CritiqueReport,
    DiagnosisReport,
    RoutingDecision
)

logger = logging.getLogger(__name__)


#@lru_cache(maxsize=4)
def _load_prompt_template(prompt_path: str, output_example: str, tools: List[BaseTool]) -> str:
    main_template_path = config.PROMPTS_DIR / f"{prompt_path}.md"
    if not main_template_path.exists():
        raise FileNotFoundError(f"Main prompt file not found: {main_template_path}")
    main_template = main_template_path.read_text()

    tool_prompts = [tool.prompt for tool in tools if tool.prompt]

    if tool_prompts:
        combined_tool_usage = "\n---\n".join(tool_prompts)
        prompt = main_template.replace("{tool_usage}", combined_tool_usage)
    else:
        prompt = main_template.replace("### Tool Usage", "")
        prompt = prompt.replace("{tool_usage}", "")

    final_prompt = prompt.format(example_json=output_example)

    return final_prompt


def _create_agent(
        prompt_path: str,
        description: str,
        response_model: Type[BaseModel],
        example: str,
        base_tools: List[BaseTool],
        custom_tools: Optional[List[BaseTool]] = None,
        model_id: Optional[str] = None,
) -> Agent:
    effective_model_id = model_id or config.DEFAULT_MODEL_ID
    model_instance = get_openrouter_client(model_id=effective_model_id)
    final_tools = base_tools + (custom_tools or [])
    formatted_prompt = _load_prompt_template(
        prompt_path=prompt_path,
        output_example = example,
        tools= final_tools
    )

    return Agent(
        model=model_instance,
        response_model=response_model,
        tools=final_tools,
        instructions=[formatted_prompt],
        description=description,
    )


def get_common_tools(kb_tool: KnowledgeBaseTools) -> List[BaseTool]:
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
        tools: List[BaseTool],
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
        base_tools=tools,
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
