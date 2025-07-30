import json
import pytest
from unittest.mock import MagicMock

from agno.agent import Agent
from pydantic import ValidationError

import agents
from data_models import (
    CritiqueReport, DiagnosisReport,
    InteractiveClarification, LearningReport,
    ModelConfig,QuickSummaryReport,
    RoutingDecision
)
from llm_catalog import CATALOG


@pytest.fixture
def model_config() -> ModelConfig:
    return ModelConfig(provider_key="OpenAI", model_key="GPT-4o Mini", model_id="gpt-4o-mini")


@pytest.fixture(autouse=True)
def mock_agno_model_classes(monkeypatch):
    mock_model_class = MagicMock()
    for provider_key in CATALOG.providers:
        provider_config = CATALOG.providers[provider_key]
        if provider_config.model_class is not None:
            monkeypatch.setattr(provider_config, 'model_class', mock_model_class)

def _validate_agent_and_prompt(
        agent_instance: Agent,
        expected_response_model: type,
        expected_tool_names: list[str]
):
    assert isinstance(agent_instance, Agent)
    assert agent_instance.response_model == expected_response_model

    prompt_text = agent_instance.instructions[0]
    assert isinstance(prompt_text, str)
    assert "{example_json}" not in prompt_text, "Example placeholder was not replaced"

    try:
        example_parts = prompt_text.split("Example Output:**\n```json\n")
        if len(example_parts) > 1:
            example_str = example_parts.split("\n```")[0]
            example_json = json.loads(example_str)
            expected_response_model(**example_json)
        else:
            pytest.fail("Could not find Example Output block in the prompt.")

    except (IndexError, json.JSONDecodeError) as e:
        pytest.fail(f"Error parsing prompt content: {e}")
    except ValidationError as e:
        pytest.fail(f"Injected example JSON is not valid for model {expected_response_model.__name__}: {e}")

    actual_tool_names = [tool.name for tool in agent_instance.tools]
    assert sorted(actual_tool_names) == sorted(expected_tool_names)

def test_get_router_agent(model_config):
    router_agent = agents.get_router_agent(model_config)
    _validate_agent_and_prompt(
        agent_instance=router_agent,
        expected_response_model=RoutingDecision,
        expected_tool_names=[]
    )


def test_get_specialist_agent_config_error(model_config):
    specialist_agent = agents.get_specialist_agent(
        agent_type="CONFIGURATION_ERROR",
        model_config=model_config
    )
    _validate_agent_and_prompt(
        agent_instance=specialist_agent,
        expected_response_model=DiagnosisReport,
        expected_tool_names=["jenkins_workspace_tools", "knowledge_base_tools"]
    )


def test_get_standard_critic_agent(model_config):
    critic_agent = agents.get_critic_agent(model_config)
    _validate_agent_and_prompt(
        agent_instance=critic_agent,
        expected_response_model=CritiqueReport,
        expected_tool_names=[]
    )


def test_get_quick_summary_agent(model_config):
    summary_agent = agents.get_quick_summary_agent(model_config)
    _validate_agent_and_prompt(
        agent_instance=summary_agent,
        expected_response_model=QuickSummaryReport,
        expected_tool_names=["jenkins_workspace_tools", "knowledge_base_tools"]
    )


def test_get_quick_summary_critic_agent(model_config):
    critic_agent = agents.get_quick_summary_critic_agent(model_config)
    _validate_agent_and_prompt(
        agent_instance=critic_agent,
        expected_response_model=CritiqueReport,
        expected_tool_names=[]
    )


def test_get_interactive_debugger_agent(model_config):
    interactive_agent = agents.get_interactive_debugger_agent(model_config)
    _validate_agent_and_prompt(
        agent_instance=interactive_agent,
        expected_response_model=InteractiveClarification,
        expected_tool_names=["jenkins_workspace_tools", "knowledge_base_tools"]
    )


def test_get_interactive_critic_agent(model_config):
    critic_agent = agents.get_interactive_critic_agent(model_config)
    _validate_agent_and_prompt(
        agent_instance=critic_agent,
        expected_response_model=CritiqueReport,
        expected_tool_names=[]
    )


def test_get_learning_agent(model_config):
    learning_agent = agents.get_learning_agent(model_config)
    _validate_agent_and_prompt(
        agent_instance=learning_agent,
        expected_response_model=LearningReport,
        expected_tool_names=["knowledge_base_tools"]
    )


def test_invalid_agent_creation_raises_error():
    bad_config = ModelConfig(provider_key="InvalidProvider", model_key="N/A", model_id="N/A")
    with pytest.raises(NotImplementedError, match="is not configured or supported"):
        agents.get_router_agent(bad_config)
