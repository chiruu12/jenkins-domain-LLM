import logging
from typing import Dict, Type
from data_models import OperatingMode
from agents import AgentFactory
from log_manager import LLMInteractionLogger

from pipelines import (
    StandardPipeline,
    SummaryPipeline,
    InteractivePipeline,
    LearningPipeline,
    BasePipeline,
)

logger = logging.getLogger(__name__)

PIPELINE_MAP: Dict[OperatingMode, Type[BasePipeline]] = {
    OperatingMode.STANDARD: StandardPipeline,
    OperatingMode.QUICK_SUMMARY: SummaryPipeline,
    OperatingMode.INTERACTIVE: InteractivePipeline,
    OperatingMode.LEARNING: LearningPipeline,
}


def create_pipeline(
        mode: OperatingMode,
        agent_factory: AgentFactory,
        llm_logger: LLMInteractionLogger,
) -> BasePipeline:
    """
    A factory function that creates and returns the appropriate pipeline instance.

    Args:
        mode: The OperatingMode enum that determines which pipeline to create.
        agent_factory: The initialized factory for creating agents.
        llm_logger: The logger for recording LLM interactions.

    Returns:
        An initialized instance of a class that inherits from BasePipeline.
    """
    logger.info(f"Factory creating pipeline for mode: {mode.value}")

    pipeline_class = PIPELINE_MAP.get(mode)
    if not pipeline_class:
        logger.error(f"No pipeline is configured for the operating mode: {mode.value}")
        raise ValueError(f"No pipeline configured for operating mode: {mode.value}")

    pipeline = pipeline_class(agent_factory, llm_logger)

    return pipeline
