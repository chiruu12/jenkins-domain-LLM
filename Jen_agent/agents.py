import logging
from typing import List, Dict
from pydantic import BaseModel
from pathlib import Path
from agno.agent import Agent
from agno.models.base import Model

import data_models
import prompt_examples
from tools.base_tool import BaseTool
from settings import settings

logger = logging.getLogger(__name__)


class AgentFactory:
    """
    A factory class responsible for assembling and caching all agents.
    """

    def __init__(self, configured_tools: Dict[str, BaseTool]):
        self.configured_tools = configured_tools
        self._agent_cache: Dict[str, Agent] = {}

    def _create_agent(
            self,
            agent_name: str,
            model: Model,
            agent_tools: List[BaseTool]
    ) -> Agent:
        """
        Internal method to build and cache an agent instance from its final components.
        """
        cache_key = f"{agent_name}_{model.name}_{model.id}"
        if cache_key in self._agent_cache:
            return self._agent_cache[cache_key]

        agent_config = settings.get_agent_config(agent_name)

        response_model = getattr(data_models, agent_config.response_model)
        example_str = getattr(prompt_examples, agent_config.example)

        prompts_dir = Path(settings.application.prompts_dir)
        prompt_path = prompts_dir / f"{agent_config.prompt_path}.md"
        template = prompt_path.read_text(encoding="utf-8")

        tool_prompts = [t.prompt for t in agent_tools if t.prompt]
        if tool_prompts:
            prompt = template.replace("{tool_usage}", "\n---\n".join(tool_prompts))
        else:
            prompt = template.replace("### Tool Usage\n\n{tool_usage}", "")

        final_prompt = prompt.format(example_json=example_str)

        agent = Agent(
            model=model,
            response_model=response_model,
            tools=agent_tools,
            instructions=[final_prompt],
        )

        self._agent_cache[cache_key] = agent
        logger.info(f"Created and cached new agent: {agent_name} with model {model.id}")
        return agent

    def _get_tools_for_agent(self, agent_name: str) -> List[BaseTool]:
        """Helper to resolve tool names from config to tool objects."""
        agent_config = settings.get_agent_config(agent_name)
        return [self.configured_tools[name] for name in agent_config.tools]

    def get_router_agent(self, model: Model) -> Agent:
        tools = self._get_tools_for_agent("router")
        return self._create_agent(agent_name="router", model=model, agent_tools=tools)

    def get_critic_agent(self, model: Model) -> Agent:
        tools = self._get_tools_for_agent("critic")
        return self._create_agent(agent_name="critic", model=model, agent_tools=tools)

    def get_specialist_agent(self, failure_category: str, model: Model) -> Agent:
        agent_name = f"specialist_{failure_category.lower()}"
        if agent_name not in settings.agents:
            agent_name = "specialist_unknown"

        tools = self._get_tools_for_agent(agent_name)
        return self._create_agent(agent_name=agent_name, model=model, agent_tools=tools)

    def get_quick_summary_agent(self, model: Model) -> Agent:
        tools = self._get_tools_for_agent("quick_summary_main")
        return self._create_agent(agent_name="quick_summary_main", model=model, agent_tools=tools)

    def get_quick_summary_critic(self, model: Model) -> Agent:
        tools = self._get_tools_for_agent("quick_summary_critic")
        return self._create_agent(agent_name="quick_summary_critic", model=model, agent_tools=tools)

    def get_interactive_agent(self, model: Model) -> Agent:
        tools = self._get_tools_for_agent("interactive_main")
        return self._create_agent(agent_name="interactive_main", model=model, agent_tools=tools)

    def get_interactive_critic(self, model: Model) -> Agent:
        tools = self._get_tools_for_agent("interactive_critic")
        return self._create_agent(agent_name="interactive_critic", model=model, agent_tools=tools)

    def get_learning_agent(self, model: Model) -> Agent:
        tools = self._get_tools_for_agent("learning_main")
        return self._create_agent(agent_name="learning_main", model=model, agent_tools=tools)
