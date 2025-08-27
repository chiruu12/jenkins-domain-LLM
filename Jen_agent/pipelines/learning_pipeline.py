import logging
from pipelines.base import BasePipeline

logger = logging.getLogger(__name__)

class LearningPipeline(BasePipeline):
    async def run(self, user_question: str) -> str:
        logger.info("--- LEARNING PIPELINE START ---")

        learner = self.agent_factory.get_learning_agent(self.model)
        learning_response = await learner.arun(message=user_question)
        self.llm_logger.log_response(learning_response)

        return learning_response.content.model_dump_json(indent=2)
