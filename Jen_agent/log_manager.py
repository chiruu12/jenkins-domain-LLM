import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

from pydantic import BaseModel
from agno.agent import RunResponse

from data_models import (
    LLMRequestLog, LLMResponseLog, LLMErrorLog, TokenUsageLog
)

logger = logging.getLogger(__name__)


def setup_application_logger(log_dir: Path, run_id: str, level: int = logging.INFO) -> None:
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"{run_id}.log"

    app_logger = logging.getLogger("JenkinsAgentApp")
    if app_logger.hasHandlers():
        app_logger.handlers.clear()

    app_logger.setLevel(level)
    app_logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    app_logger.addHandler(file_handler)

    lightrag_logger = logging.getLogger("lightrag")
    if lightrag_logger.hasHandlers():
        lightrag_logger.handlers.clear()
    lightrag_logger.setLevel(level)
    lightrag_logger.propagate = False
    lightrag_logger.addHandler(file_handler)

class LLMInteractionLogger:
    def __init__(self, log_dir: Path, run_id: str):
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"{run_id}.log"

        self._logger = logging.getLogger("LLMInteractionLogger")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False

        if self._logger.hasHandlers():
            self._logger.handlers.clear()

        handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s\n%(message)s\n---', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)

        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.last_call_input_tokens: int = 0
        self.last_call_output_tokens: int = 0

    def _log_structured_message(self, log_model: BaseModel):
        self._logger.debug(log_model.model_dump_json(indent=2))

    def log_request(self, model_id: str, messages: List[Dict[str, Any]], tools: Optional[List[str]] = None):
        log_entry = LLMRequestLog(
            model_id=model_id, tools=tools or [], messages=messages
        )
        self._log_structured_message(log_entry)

    def log_response(self, response: RunResponse):
        model_id = "unknown_model"
        try:
            model_id = response.model
            usage_metrics = response.metrics or {}
            content = response.content

            messages = []
            if response.messages:
                for msg in response.messages:
                    logged_metrics = None

                    if msg.metrics:
                        if msg.role == "assistant":
                            clean_metrics = vars(msg.metrics).copy()
                            clean_metrics.pop('timer', None)
                            logged_metrics = clean_metrics

                    messages.append({
                        "role": msg.role,
                        "content": msg.content,
                        "tool_calls": msg.tool_calls,
                        "metrics": logged_metrics
                    })

            input_tokens = sum(usage_metrics.get("input_tokens", []))
            output_tokens = sum(usage_metrics.get("output_tokens", []))

            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.last_call_input_tokens = input_tokens
            self.last_call_output_tokens = output_tokens

            token_log = TokenUsageLog(
                call_input_tokens=input_tokens,
                call_output_tokens=output_tokens,
                cumulative_input_tokens=self.total_input_tokens,
                cumulative_output_tokens=self.total_output_tokens,
            )

            response_log = LLMResponseLog(
                model_id=model_id,
                final_content=content.model_dump_json(indent=2) if content else None,
                token_usage=token_log,
                full_message_history=messages
            )
            self._log_structured_message(response_log)

        except Exception as e:
            self.log_error(
                model_id=model_id,
                error_message=f"Failed to parse agno RunResponse object. Error: {e}",
                raw_response=str(response)
            )

    def log_error(self, model_id: str, error_message: str, raw_response: Optional[str] = None):
        error_log = LLMErrorLog(
            model_id=model_id,
            error_message=error_message,
            raw_response=raw_response
        )
        self._log_structured_message(error_log)

    def get_summary(self) -> str:
        return (
            f"Total Input Tokens: {self.total_input_tokens} | "
            f"Total Output Tokens: {self.total_output_tokens}"
        )

    def get_last_turn_summary(self) -> str:
        return (
            f"Last Turn - Input Tokens: {self.last_call_input_tokens} | "
            f"Output Tokens: {self.last_call_output_tokens}"
        )