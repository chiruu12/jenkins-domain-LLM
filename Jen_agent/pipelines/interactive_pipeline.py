from typing import Any, Union
from pipelines.base import BasePipeline
from data_models import (
    InitialLogInput,
    InitialInteractiveInput,
    FollowupInput
)


class InteractivePipeline(BasePipeline):
    async def run(self, pipeline_input: Union[InitialLogInput, InitialInteractiveInput]) -> Any:
        if not isinstance(pipeline_input, InitialInteractiveInput):
            return {"error": "Interactive pipeline requires InitialInteractiveInput."}

        followup_input = FollowupInput(**pipeline_input.model_dump())
        return await self.run_followup(followup_input)

    async def run_followup(self, followup_input: FollowupInput) -> Any:
        full_prompt = self._construct_prompt_with_memory(
            followup_input.user_input,
            followup_input.short_term_history,
            followup_input.long_term_memory
        )
        debugger = self.agent_factory.get_interactive_agent(self.model)
        critic = self.agent_factory.get_interactive_critic(self.model)
        chained_agent = debugger + critic
        return await chained_agent.arun(full_prompt, self.llm_logger)
