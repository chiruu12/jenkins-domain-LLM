import logging
from pathlib import Path
from .base_tool import BaseTool
from models.base import BaseProvider
from agno.agent import Agent
from agno.tools.mcp import MCPTools
from settings import settings, MCPSettings

logger = logging.getLogger(__name__)

class JenkinsMCPTool(BaseTool):
    """
    A tool that encapsulates a dedicated agent to interact with a live
    Jenkins instance via the MCP server plugin.
    """

    def __init__(self, name: str, provider: BaseProvider, model_id: str, config: MCPSettings):
        super().__init__(name=name)
        self.provider = provider
        self.model_id = model_id
        self.config = config

        self._mcp_tools: MCPTools | None = None
        self._mcp_agent: Agent | None = None

        self.register(self.execute_jenkins_command)
        logger.info(f"JenkinsMCPTool '{name}' configured for server '{self.config.server_url}'.")

    def _load_internal_agent_instructions(self) -> str:
        """Loads the dedicated instructions for the internal MCP agent from the path specified in the config."""
        prompt_path = Path(settings.application.prompts_dir) / self.config.internal_agent_prompt_path
        if not prompt_path.exists():
            logger.error(f"Internal agent instructions not found at: {prompt_path}")
            return "You are an agent that executes Jenkins commands."
        return prompt_path.read_text(encoding="utf-8")

    async def __aenter__(self):
        """Initializes the async context."""
        logger.info("Initializing MCP connection and internal agent...")
        self._mcp_tools = MCPTools(url=self.config.server_url, transport="sse")
        await self._mcp_tools.__aenter__()

        instructions = self._load_internal_agent_instructions()
        mcp_model = self.provider.get_chat_model(self.model_id)
        self._mcp_agent = Agent(
            model=mcp_model,
            tools=[self._mcp_tools],
            instructions=[instructions]
        )
        logger.info("MCP connection and internal agent are ready.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleans up the async context, ensuring the MCP connection is closed."""
        logger.info("Closing MCP connection...")
        if self._mcp_tools:
            await self._mcp_tools.__aexit__(exc_type, exc_val, exc_tb)
        logger.info("MCP connection closed.")

    async def execute_jenkins_command(self, instructions: str) -> str:
        """
        Executes a natural language command by passing it to the internal agent.
        """
        if not self._mcp_agent:
            raise RuntimeError("MCP Tool is not initialized. Use 'async with' syntax.")

        logger.info(f"MCP Tool passing instructions to internal agent: '{instructions}'")
        try:
            response = await self._mcp_agent.arun(message=instructions)
            return str(response.content)
        except Exception as e:
            logger.error(f"Internal MCP agent failed to execute command: {e}", exc_info=True)
            return f"Error: Failed to execute Jenkins command. Reason: {e}"
