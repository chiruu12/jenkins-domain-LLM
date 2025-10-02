from typing import Any, Union
from pipelines.base import BasePipeline
from data_models import (
    InitialLogInput,
    InitialInteractiveInput,
    FollowupInput)


class LearningPipeline(BasePipeline):
    async def run(self, pipeline_input: Union[InitialLogInput, InitialInteractiveInput]) -> Any:
        if not isinstance(pipeline_input, InitialInteractiveInput):
            return {"error": "Learning pipeline requires InitialInteractiveInput."}

        followup_input = FollowupInput(user_input=pipeline_input.user_input, **pipeline_input.model_dump())
        return await self.run_followup(followup_input)

    async def run_followup(self, followup_input: FollowupInput) -> Any:
        full_prompt = self._construct_prompt_with_memory(
            followup_input.user_input,
            followup_input.short_term_history,
            followup_input.long_term_memory
        )
        learner = self.agent_factory.get_learning_agent(self.model)
        response = await learner.arun(message=full_prompt)
        self.llm_logger.log_response(response)
        return response.content
