import os
import logging
from pathlib import Path
from .base_tool import BaseTool
from sanitizer import ContentSanitizer, CredentialMapper

logger = logging.getLogger(__name__)


class JenkinsWorkspaceTools(BaseTool):
    """
    A secure tool for listing and reading files within a sandboxed Jenkins build workspace.
    Path traversal outside the workspace is strictly forbidden. All file content is automatically
    sanitized to remove credentials and secrets before being returned.
    """

    def __init__(
            self,
            base_directory_path: str,
            sanitizer: ContentSanitizer,
            mapper: CredentialMapper
    ):
        super().__init__(name="jenkins_workspace_tools")

        self.base_path = Path(base_directory_path).resolve()
        if not self.base_path.is_dir():
            raise FileNotFoundError(f"The specified base workspace directory does not exist: {self.base_path}")

        self.sanitizer = sanitizer
        self.mapper = mapper

        self.register(self.list_files_in_workspace)
        self.register(self.read_file_from_workspace)
        logger.info(f"JenkinsWorkspaceTools initialized for directory: '{self.base_path}'")

    def _is_path_safe(self, path_to_check: Path) -> bool:
        """
        Verifies that the resolved path is within the designated base workspace directory.
        """
        try:
            path_to_check.resolve().is_relative_to(self.base_path)
            return True
        except ValueError:
            return False

    def list_files_in_workspace(self, subdirectory: str = ".") -> str:
        """
        Lists all files and directories within the build workspace, starting from a given subdirectory.
        Defaults to listing the entire workspace.
        """
        target_dir = self.base_path.joinpath(subdirectory)

        if not self._is_path_safe(target_dir):
            logger.warning(f"SECURITY: Agent attempted path traversal to '{subdirectory}'. Access denied.")
            return "Error: Access denied. Path traversal is not permitted."

        if not target_dir.is_dir():
            return f"Error: Directory '{subdirectory}' not found within the workspace."

        tree_lines = []
        for root, _, files in os.walk(target_dir):
            root_path = Path(root)
            level = len(root_path.relative_to(target_dir).parts)
            indent = "    " * level
            tree_lines.append(f"{indent}📁 {root_path.relative_to(self.base_path)}/")

            sub_indent = "    " * (level + 1)
            for f in sorted(files):
                tree_lines.append(f"{sub_indent}📄 {f}")

        if not tree_lines:
            return "Directory is empty."

        return "\n".join(tree_lines)

    def read_file_from_workspace(self, file_path: str) -> str:
        """
        Reads and returns the sanitized content of a single file from the workspace.
        """
        target_file = self.base_path.joinpath(file_path)

        if not self._is_path_safe(target_file):
            logger.warning(f"SECURITY: Agent attempted path traversal to read '{file_path}'. Access denied.")
            return "Error: Access denied. Path traversal is not permitted."

        if not target_file.is_file():
            return f"Error: File not found at '{file_path}'."

        try:
            logger.info(f"Reading file: {target_file}")
            raw_content = target_file.read_text(encoding="utf-8", errors="ignore")

            logger.info(f"Sanitizing {len(raw_content)} characters from '{file_path}'...")
            sanitized_content = self.sanitizer.sanitize(raw_content, self.mapper)

            return sanitized_content
        except Exception as e:
            logger.error(f"Error reading file '{file_path}': {e}", exc_info=True)
            return f"Error: An unexpected error occurred while reading the file: {e}"
