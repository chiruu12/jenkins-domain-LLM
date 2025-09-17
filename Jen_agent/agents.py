import logging
from typing import List, Dict
from pathlib import Path
import data_models
import prompt_examples
from tools.base_tool import BaseTool
from settings import settings
from agno.agent import Agent
from agno.models.base import Model
from data_models import DiagnosisReport, CritiqueReport, QuickSummaryReport, InteractiveClarification

logger = logging.getLogger(__name__)

class ChainedAgent:
    def __init__(self, main_agent: 'BaseAgent', critic_agent: 'BaseAgent'):
        self.main_agent = main_agent
        self.critic_agent = critic_agent
        self.model = main_agent.model

    async def arun(self, message: str, llm_logger) -> str:
        last_report = None
        max_retries = 2
        for attempt in range(max_retries):
            logger.info(f"Chained execution: Main agent attempt {attempt + 1}/{max_retries}...")
            draft_response = await self.main_agent.arun(message=message)
            llm_logger.log_response(draft_response)

            if not isinstance(draft_response.content, (DiagnosisReport, QuickSummaryReport, InteractiveClarification)):
                logger.error("Main agent failed to produce a valid Pydantic object. Retrying with feedback.")
                feedback = "\n\nCRITICAL FEEDBACK: Your previous response was not in the correct format. You MUST respond with a valid JSON object."
                message += feedback
                continue

            last_report = draft_response.content

            logger.info(f"Chained execution: Critic agent is reviewing...")
            critique_prompt = f"Please review this report:\n\n{last_report.model_dump_json()}"
            critique_response = await self.critic_agent.arun(message=critique_prompt)
            llm_logger.log_response(critique_response)

            if not isinstance(critique_response.content, CritiqueReport):
                logger.warning("Critic failed to produce a valid critique. Approving last report.")
                break

            critique = critique_response.content
            logger.info(f"Critic review: Approved={critique.is_approved}, Feedback='{critique.critique}'")

            if critique.is_approved:
                break
            else:
                feedback = f"\n\nA previous attempt was critiqued: '{critique.critique}'. Address this and generate an improved report."
                message += feedback

        return last_report.model_dump_json(indent=2) if last_report else "{}"


class BaseAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info(f"Initialized agent with ID: {self.agent_id} for model: {self.model.id}")

    def __add__(self, other_agent: 'BaseAgent') -> ChainedAgent:
        if not isinstance(other_agent, BaseAgent):
            raise TypeError("Can only chain BaseAgent instances.")
        logger.info(f"Chaining agent {self.agent_id} (main) with {other_agent.agent_id} (critic).")
        return ChainedAgent(main_agent=self, critic_agent=other_agent)

    async def arun(self, *args, **kwargs):
        try:
            return await super().arun(*args, **kwargs)
        except Exception as e:
            logger.error(f"Agent {self.agent_id} encountered an unhandled exception during arun: {e}", exc_info=True)
            return '{"error": "Agent execution failed unexpectedly. Check application logs for details."}'

class AgentFactory:
    """
    A factory class responsible for assembling and caching all agents.
    """

    def __init__(self, configured_tools: Dict[str, BaseTool]):
        self.configured_tools = configured_tools
        self._agent_cache: Dict[str, BaseAgent] = {}

    def _create_agent(
            self,
            agent_name: str,
            model: Model,
            agent_tools: List[BaseTool]
    ) -> BaseAgent:
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
        tool_usage_str = "\n---\n".join(tool_prompts) if tool_prompts else ""

        if not tool_usage_str:
            template = template.replace("### Tool Usage", "")

        final_prompt = template.format(
            example_json=example_str,
            tool_usage=tool_usage_str
        )

        agent = BaseAgent(
            model=model,
            response_model=response_model,
            tools=agent_tools,
            instructions=[final_prompt],
        )

        self._agent_cache[cache_key] = agent
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
