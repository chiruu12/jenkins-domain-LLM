from pathlib import Path
from agno.tools import Toolkit

class BaseTool(Toolkit):
    def __init__(self, name: str, prompt_dir: Path):
        super().__init__(name=name)
        self.prompts_dir = prompt_dir
        self.prompt = self._load_tool_prompt()

    def _load_tool_prompt(self) -> str:
        prompt_path = self.prompts_dir / "tools" / f"{self.name}.md"
        return prompt_path.read_text() if prompt_path.exists() else ""
