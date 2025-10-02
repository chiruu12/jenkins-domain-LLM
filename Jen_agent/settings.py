import os
from typing import Dict, List, Optional, Union
import yaml
from pydantic import BaseModel, Field

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config', 'config.yaml')


class DefaultsSettings(BaseModel):
    provider: str
    chat_model: str
    embedding_model: str
    use_reranker: bool
    reranker_provider: Optional[str] = None
    reranker_model: Optional[str] = None


class ProviderSettings(BaseModel):
    module: str
    class_name: str
    init_args: Dict[str, str] = Field(default_factory=dict)


class ApplicationSettings(BaseModel):
    prompts_dir: str


class RagSettings(BaseModel):
    working_dir: str
    embedding_provider: str
    embedding_model: str
    llm_provider: str
    llm_model: str
    task_type: str


class ToolSettings(BaseModel):
    module: str
    class_name: str

class MCPSettings(ToolSettings):
    server_url: str = "http://localhost:8000/sse"
    internal_agent_prompt_path: str

class AgentSettings(BaseModel):
    prompt_path: str
    response_model: str
    example: str
    tools: List[str] = Field(default_factory=list)

class MemorySettings(BaseModel):
    """Configuration for the cross-session conversation memory."""
    working_dir: str
    embedding_provider: str
    embedding_model: str
    task_type: str

class Settings(BaseModel):
    defaults: DefaultsSettings
    providers: Dict[str, ProviderSettings]
    application: ApplicationSettings
    rag_settings: RagSettings
    memory_settings: MemorySettings
    tools: Dict[str, Union[MCPSettings, ToolSettings]]
    agents: Dict[str, AgentSettings]

    def get_agent_config(self, agent_name: str) -> AgentSettings:
        agent_conf = self.agents.get(agent_name)
        if not agent_conf:
            raise ValueError(f"Agent '{agent_name}' not found in configuration.")
        return agent_conf

    def get_tool_config(self, tool_name: str) -> Union[MCPSettings, ToolSettings]:
        tool_conf = self.tools.get(tool_name)
        if not tool_conf:
            raise ValueError(f"Tool '{tool_name}' not found in configuration.")
        return tool_conf

    def get_tools_for_agent(self, agent_name: str) -> Dict[str, ToolSettings]:
        agent_config = self.get_agent_config(agent_name)
        tool_names = agent_config.tools
        return {name: self.get_tool_config(name) for name in tool_names}


def load_settings() -> Settings:
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Configuration file not found at: {CONFIG_PATH}")

    with open(CONFIG_PATH, 'r') as f:
        config_data = yaml.safe_load(f)

    return Settings(**config_data)


settings = load_settings()
