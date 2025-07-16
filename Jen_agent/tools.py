import os
from pathlib import Path
from agno.tools import Toolkit


class JenkinsWorkspaceTools(Toolkit):
    def __init__(self, base_directory_path: str):
        super().__init__(name="jenkins_workspace_tools")
        self._base_path = None
        self.base_path = base_directory_path
        self.register(self.read_file_from_workspace)

    @property
    def base_path(self) -> Path:
        return self._base_path

    @base_path.setter
    def base_path(self, value: str):
        resolved_path = Path(value).resolve()
        if not resolved_path.is_dir():
            raise ValueError(f"Base directory does not exist or is not a directory: {resolved_path}")
        self._base_path = resolved_path

    def read_file_from_workspace(self, file_path: str) -> str:
        try:
            target_path = self.base_path.joinpath(file_path)
            resolved_target_path = target_path.resolve()

            if os.path.commonpath([self.base_path, resolved_target_path]) != str(self.base_path):
                return "Error: Path traversal detected. Access denied."

            if not resolved_target_path.is_file():
                return f"Error: File not found at '{file_path}'."

            return resolved_target_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return f"An unexpected error occurred while reading '{file_path}': {e}"

#TODO: add the RAG tool
class KnowledgeBaseTools(Toolkit):
    def __init__(self):
        super().__init__(name="knowledge_base_tools")
        self.register(self.query_knowledge_base)

    def query_knowledge_base(self, query: str) -> str:
        "This is a placeholder for querying a knowledge base(RAG)."
        return "Placeholder"

#TODO: add the MCP tool
class Jenkins_MCPToo(Toolkit):
    def __init__(self):
        super().__init__(name="jenkins_mcp_tool")
        self.register(self.query_mcp)

    def query_mcp(self, query: str) -> str:
        "This is a placeholder for querying the MCP."
        return "Placeholder"
