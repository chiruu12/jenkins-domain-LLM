import json
from typing import Any, List, Optional, Type
from agno.agent import Agent
from agno.tools import Toolkit
from pydantic import BaseModel

import config
import prompt_examples
from data_models import (
    CritiqueReport, DiagnosisReport,
    InteractiveClarification, LearningReport,
    ModelConfig, QuickSummaryReport,
    RoutingDecision
)
from llm_catalog import CATALOG
from tools import JenkinsWorkspaceTools, KnowledgeBaseTools


def _load_and_format_prompt(prompt_path: str, response_model: Type[BaseModel], example: str) -> str:
    """Loads a prompt template and injects the JSON schema and an example."""
    full_path = config.PROMPTS_DIR / f"{prompt_path}.md"
    if not full_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {full_path}")

    template = full_path.read_text()
    schema = json.dumps(response_model.model_json_schema(), indent=2)
    return template.format(schema_json=schema, example_json=example)


def _create_agent(
        prompt_path: str,
        description: str,
        response_model: Type[BaseModel],
        example: str,
        model_config: ModelConfig,
        base_tools: List[Toolkit],
        custom_tools: Optional[List[Toolkit]] = None,
        **model_kwargs: Any,
) -> Agent:
    """A private helper factory to create and configure an agent."""
    provider_config = CATALOG.providers.get(model_config.provider_key)
    if not provider_config or not provider_config.model_class:
        raise NotImplementedError(
            f"Provider '{model_config.provider_key}' is not configured or supported in the catalog."
        )

    model_instance = provider_config.model_class(id=model_config.model_id, **model_kwargs)

    final_tools = base_tools + (custom_tools or [])

    formatted_prompt = _load_and_format_prompt(prompt_path, response_model, example)

    return Agent(
        model=model_instance,
        response_model=response_model,
        tools=final_tools,
        instructions=[formatted_prompt],
        description=description,
    )


def get_common_tools() -> List[Toolkit]:
    """Returns a list of tools common to most diagnostic agents."""
    return [JenkinsWorkspaceTools(base_directory_path="."), KnowledgeBaseTools()]

def get_router_agent(model_config: ModelConfig, **kwargs) -> Agent:
    """Creates the agent that classifies the failure type."""
    return _create_agent(
        prompt_path="standard/router",
        description="Classifies the failure type.",
        response_model=RoutingDecision,
        example=prompt_examples.ROUTING_EXAMPLE,
        model_config=model_config,
        base_tools=[],
        **kwargs
    )


def get_specialist_agent(agent_type: str, model_config: ModelConfig, **kwargs) -> Agent:
    """Creates a specialist agent based on the failure category."""
    prompt_map = {
        "CONFIGURATION_ERROR": "config_error", "TEST_FAILURE": "test_failure",
        "DEPENDENCY_ERROR": "dependency_error", "INFRA_FAILURE": "infra_failure", "UNKNOWN": "default",
    }
    prompt_name = prompt_map.get(agent_type, "default")

    return _create_agent(
        prompt_path=f"standard/{prompt_name}",
        description=f"Diagnoses {agent_type}",
        response_model=DiagnosisReport,
        example=prompt_examples.DIAGNOSIS_EXAMPLE,
        model_config=model_config,
        base_tools=get_common_tools(),
        **kwargs
    )


def get_critic_agent(model_config: ModelConfig, **kwargs) -> Agent:
    """Creates the agent that reviews and critiques diagnoses."""
    return _create_agent(
        prompt_path="standard/critic",
        description="Reviews diagnosis reports for quality.",
        response_model=CritiqueReport,
        example=prompt_examples.CRITIQUE_EXAMPLE,
        model_config=model_config,
        base_tools=[],
        **kwargs
    )

def get_quick_summary_agent(model_config: ModelConfig, **kwargs) -> Agent:
    """Creates an agent that provides a brief summary of the failure."""
    return _create_agent(
        prompt_path="quick_summary/main",
        description="Provides a brief root cause summary.",
        response_model=QuickSummaryReport,
        example=prompt_examples.QUICK_SUMMARY_EXAMPLE,
        model_config=model_config,
        base_tools=get_common_tools(),
        **kwargs
    )


def get_interactive_debugger_agent(model_config: ModelConfig, **kwargs) -> Agent:
    """Creates an agent that asks clarifying questions."""
    return _create_agent(
        prompt_path="interactive/main",
        description="Asks clarifying questions for debugging.",
        response_model=InteractiveClarification,
        example=prompt_examples.INTERACTIVE_EXAMPLE,
        model_config=model_config,
        base_tools=get_common_tools(),
        **kwargs
    )


def get_learning_agent(model_config: ModelConfig, **kwargs) -> Agent:
    """Creates an agent that explains Jenkins concepts."""
    return _create_agent(
        prompt_path="learning/main",
        description="Explains Jenkins concepts.",
        response_model=LearningReport,
        example=prompt_examples.LEARNING_EXAMPLE,
        model_config=model_config,
        base_tools=[KnowledgeBaseTools()],
        **kwargs
    )


def get_quick_summary_critic_agent(model_config: ModelConfig, **kwargs) -> Agent:
    """Creates a critic agent for reviewing QuickSummaryReport objects."""
    return _create_agent(
        prompt_path="quick_summary/critic",
        description="Reviews a QuickSummaryReport for brevity and format.",
        response_model=CritiqueReport,
        example=prompt_examples.QUICK_SUMMARY_CRITIQUE_EXAMPLE,
        model_config=model_config,
        base_tools=[],
        **kwargs
    )


def get_interactive_critic_agent(model_config: ModelConfig, **kwargs) -> Agent:
    """Creates a critic agent for reviewing InteractiveClarification objects."""
    return _create_agent(
        prompt_path="interactive/critic",
        description="Reviews an InteractiveClarification to ensure it asks a valid question.",
        response_model=CritiqueReport,
        example=prompt_examples.INTERACTIVE_CRITIQUE_EXAMPLE,
        model_config=model_config,
        base_tools=[],
        **kwargs
    )

