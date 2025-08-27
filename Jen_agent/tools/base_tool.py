from abc import ABC
from pathlib import Path
from agno.tools import Toolkit
from settings import settings

class BaseTool(Toolkit, ABC):
    def __init__(self, name: str):
        super().__init__(name=name)
        self.prompt = self._load_tool_prompt()

    def _load_tool_prompt(self) -> str:
        prompt_path = Path(settings.application.prompts_dir) / "tools" / f"{self.name}.md"
        if prompt_path.exists():
            return prompt_path.read_text()
        return ""
