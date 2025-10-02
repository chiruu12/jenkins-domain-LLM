from typing import Any, Union
from pipelines.base import BasePipeline
from data_models import (
    InitialLogInput,
    InitialInteractiveInput,
    FollowupInput
)


class SummaryPipeline(BasePipeline):
    async def run(self, pipeline_input: Union[InitialLogInput, InitialInteractiveInput]) -> Any:
        if not isinstance(pipeline_input, InitialLogInput):
            return {"error": "Summary pipeline requires InitialLogInput."}

        self.session_state["enable_self_correction"] = pipeline_input.enable_self_correction
        followup_input = FollowupInput(user_input=pipeline_input.raw_log, **pipeline_input.model_dump())
        return await self.run_followup(followup_input)

    async def run_followup(self, followup_input: FollowupInput) -> Any:
        enable_self_correction = self.session_state.get("enable_self_correction", True)
        full_prompt = self._construct_prompt_with_memory(
            followup_input.user_input,
            followup_input.short_term_history,
            followup_input.long_term_memory
        )
        summarizer = self.agent_factory.get_quick_summary_agent(self.model)

        if not enable_self_correction:
            response = await summarizer.arun(message=full_prompt)
            self.llm_logger.log_response(response)
            return response.content

        critic = self.agent_factory.get_quick_summary_critic(self.model)
        chained_agent = summarizer + critic
        return await chained_agent.arun(full_prompt, self.llm_logger)