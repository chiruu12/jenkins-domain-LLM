import logging
from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class LogAccessTools(BaseTool):
    """
    A tool to access different versions of the build log.
    Use this to get the complete sanitized log or the original, raw log if needed.
    """

    def __init__(self):
        super().__init__(name="log_access_tools")
        self._sanitized_log_content: str = "Sanitized log content has not been set."
        self._raw_log_content: str = "Raw log content has not been set."

        self.register(self.get_filtered_logs)
        self.register(self.get_unfiltered_logs)

    def set_log_contents(self, sanitized_log: str, raw_log: str):
        """
        An internal method to load both log versions into the tool.
        This is called by the application pipeline, not the LLM.
        """

        self._sanitized_log_content = sanitized_log
        self._raw_log_content = raw_log

    def get_filtered_logs(self) -> str:
        """
        Retrieves the entire SANITIZED build log. This is the primary log for analysis.
        """
        logger.info("Agent requested the full sanitized log content.")
        if self._sanitized_log_content == "Sanitized log content has not been set.":
            logger.warning("Agent tried to access sanitized log before it was set.")

        return self._sanitized_log_content

    def get_unfiltered_logs(self, reason: str) -> str:
        """
        Retrieves the original, raw, unfiltered log file, including all timestamps and ANSI codes.
        Use this ONLY if you suspect the sanitization process removed critical information.
        """
        logger.info(f"Agent requested the raw, unfiltered log content. Reason: {reason}")
        if self._raw_log_content == "Raw log content has not been set.":
            logger.warning("Agent tried to access raw log before it was set.")

        return self._raw_log_content
