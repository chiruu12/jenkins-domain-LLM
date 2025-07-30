import logging
from agno.tools import Toolkit

logger = logging.getLogger(__name__)

class LogAccessTools(Toolkit):
    def __init__(self):
        super().__init__(name="log_access_tools")
        self._full_log_content: str = "Log content has not been set."
        self.register(self.get_full_log)

    def set_log_content(self, log_content: str):
        self._full_log_content = log_content
        logger.info(f"Full log content ({len(log_content)} chars) has been set in LogAccessTools.")

    def get_full_log(self) -> str:
        logger.info("Agent requested the full log content.")
        return self._full_log_content
