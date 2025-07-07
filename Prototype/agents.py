from pathlib import Path
from typing import List, Type, Optional

from pydantic import BaseModel
from agno.agent import Agent
from agno.models.openrouter import OpenRouter
from agno.tools import Toolkit

import config
from data_models import (
    RoutingDecision,
    DiagnosisReport,
    CritiqueReport
)
from tools import JenkinsWorkspaceTools, KnowledgeBaseTools


def load_prompt(name: str) -> str:
    """Loads a prompt template from the configured prompts directory."""
    prompt_path = Path(config.PROMPTS_DIR) / f"{name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text()


def get_common_tools() -> List[Toolkit]:
    """Returns a list of tools common to most diagnostic agents."""
    return [
        JenkinsWorkspaceTools(base_directory_path="."),
        KnowledgeBaseTools(),
    ]


def _create_agent(
    prompt_name: str,
    description: str,
    response_model: Type[BaseModel],
    base_tools: List[Toolkit],
    custom_tools: Optional[List[Toolkit]] = None,
    model_id: Optional[str] = None,
) -> Agent:
    """A private helper factory to create and configure an agent."""
    final_tools = base_tools + (custom_tools or [])
    effective_model_id = model_id if model_id else config.DEFAULT_MODEL_ID

    if not config.API_KEY:
        raise ValueError("OPENROUTER_API_KEY is not set in the environment.")

    return Agent(
        model=OpenRouter(id=effective_model_id, api_key=config.API_KEY),
        response_model=response_model,
        tools=final_tools,
        instructions=[load_prompt(prompt_name)],
        description=description,
    )


def get_router_agent(model_id: Optional[str] = None) -> Agent:
    """Creates the agent responsible for classifying the failure type."""
    return _create_agent(
        prompt_name="router",
        description="Classifies the type of Jenkins build failure into a structured object.",
        response_model=RoutingDecision,
        base_tools=[],
        model_id=model_id,
    )


def get_config_error_agent(
    custom_tools: Optional[List[Toolkit]] = None, model_id: Optional[str] = None
) -> Agent:
    """Creates the agent for diagnosing configuration errors."""
    return _create_agent(
        prompt_name="config_error",
        description="Diagnoses build failures caused by misconfigured files like Jenkinsfile or build.xml.",
        response_model=DiagnosisReport,
        base_tools=get_common_tools(),
        custom_tools=custom_tools,
        model_id=model_id,
    )


def get_test_failure_agent(
    custom_tools: Optional[List[Toolkit]] = None, model_id: Optional[str] = None
) -> Agent:
    """Creates the agent for diagnosing test failures."""
    return _create_agent(
        prompt_name="test_failure",
        description="Diagnoses build failures caused by failing unit or integration tests.",
        response_model=DiagnosisReport,
        base_tools=get_common_tools(),
        custom_tools=custom_tools,
        model_id=model_id,
    )


def get_dependency_error_agent(
    custom_tools: Optional[List[Toolkit]] = None, model_id: Optional[str] = None
) -> Agent:
    """Creates the agent for diagnosing dependency errors."""
    return _create_agent(
        prompt_name="dependency_error",
        description="Diagnoses build failures caused by dependency resolution or repository issues.",
        response_model=DiagnosisReport,
        base_tools=get_common_tools(),
        custom_tools=custom_tools,
        model_id=model_id,
    )


def get_infra_failure_agent(
    custom_tools: Optional[List[Toolkit]] = None, model_id: Optional[str] = None
) -> Agent:
    """Creates the agent for diagnosing infrastructure failures."""
    return _create_agent(
        prompt_name="infra_failure",
        description="Diagnoses build failures caused by Jenkins infrastructure (e.g., agent offline, disk space).",
        response_model=DiagnosisReport,
        base_tools=get_common_tools(),
        custom_tools=custom_tools,
        model_id=model_id,
    )


def get_default_agent(
    custom_tools: Optional[List[Toolkit]] = None, model_id: Optional[str] = None
) -> Agent:
    """Creates the general-purpose agent for unknown failure types."""
    return _create_agent(
        prompt_name="default",
        description="A general-purpose agent for diagnosing failures of an unknown category.",
        response_model=DiagnosisReport,
        base_tools=get_common_tools(),
        custom_tools=custom_tools,
        model_id=model_id,
    )


def get_critic_agent(model_id: Optional[str] = None) -> Agent:
    """Creates the agent that reviews and critiques diagnoses."""
    return _create_agent(
        prompt_name="critic",
        description="Reviews diagnosis reports for quality and returns a structured critique.",
        response_model=CritiqueReport,
        base_tools=[],
        model_id=model_id,
    )
