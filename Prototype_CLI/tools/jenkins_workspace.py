import os
import logging
from pathlib import Path
from agno.tools import Toolkit

logger = logging.getLogger(__name__)

class JenkinsWorkspaceTools(Toolkit):
    def __init__(self, base_directory_path: str):
        super().__init__(name="jenkins_workspace_tools")
        self._base_path = Path.cwd()
        self.base_path = base_directory_path
        self.register(self.read_file_from_workspace)
        self.register(self.list_files_in_workspace)
        logger.info(f"JenkinsWorkspaceTools initialized for directory: '{self.base_path}'")

    @property
    def base_path(self) -> Path:
        return self._base_path

    @base_path.setter
    def base_path(self, value: str):
        try:
            resolved_path = Path(value).resolve()
            if not resolved_path.is_dir():
                resolved_path.mkdir(parents=True, exist_ok=True)
            self._base_path = resolved_path
        except Exception as e:
            logger.error(f"Failed to set base path to '{value}': {e}", exc_info=True)
            raise ValueError(f"Base directory could not be resolved or created: {value}")

    def read_file_from_workspace(self, file_path: str) -> str:
        logger.info(f"Attempting to read file from workspace: '{file_path}'")
        try:
            target_path = self.base_path.joinpath(file_path).resolve()

            if self.base_path not in target_path.parents and target_path != self.base_path:
                logger.warning(f"Path traversal detected for file: '{file_path}'")
                return "Error: Path traversal detected. Access denied."

            if not target_path.is_file():
                logger.warning(f"File not found at resolved path: '{target_path}'")
                return f"Error: File not found at '{file_path}'."

            content = target_path.read_text(encoding="utf-8", errors="ignore")
            logger.info(f"Successfully read {len(content)} characters from '{file_path}'")
            return content
        except Exception as e:
            logger.error(f"Unexpected error while reading '{file_path}': {e}", exc_info=True)
            return f"An unexpected error occurred while reading '{file_path}': {e}"

    def list_files_in_workspace(self, subdirectory: str = None) -> str:
        try:
            start_path = self.base_path
            if subdirectory:
                start_path = (self.base_path / subdirectory).resolve()

            if self.base_path not in start_path.parents and start_path != self.base_path:
                return "Error: Path traversal detected. Access denied."

            if not start_path.is_dir():
                return f"Error: Directory '{subdirectory or '.'}' not found."

            tree_lines = []
            for root, dirs, files in os.walk(start_path):
                level = Path(root).relative_to(start_path).parts
                indent = "    " * len(level)

                dir_display_path = Path(root).relative_to(self.base_path)
                tree_lines.append(f"{indent}📁 {dir_display_path}/")

                sub_indent = "    " * (len(level) + 1)
                for f in sorted(files):
                    file_display_path = dir_display_path / f
                    tree_lines.append(f"{sub_indent}📄 {file_display_path}")

            if len(tree_lines) > 100:
                tree_lines = tree_lines[:100]
                tree_lines.append("\n[... Output truncated due to excessive file count ...]")

            return "\n".join(tree_lines) if tree_lines else "Directory is empty."
        except Exception as e:
            logger.error(f"Error listing files in '{subdirectory or '.'}': {e}", exc_info=True)
            return f"An unexpected error occurred while listing files: {e}"