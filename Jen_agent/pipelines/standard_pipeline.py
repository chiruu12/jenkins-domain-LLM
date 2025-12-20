import logging
import json
from typing import Any, Union
from .base import BasePipeline
from data_models import (
    RoutingDecision, DiagnosisReport, InitialLogInput,
    InitialInteractiveInput, FollowupInput
)

logger = logging.getLogger("JenkinsAgentApp")


class StandardPipeline(BasePipeline):
    async def run(self, pipeline_input: Union[InitialLogInput, InitialInteractiveInput]) -> Any:
        if not isinstance(pipeline_input, InitialLogInput):
            return {"error": "Standard pipeline requires InitialLogInput."}

        logger.info("--- STANDARD DIAGNOSIS PIPELINE (INITIAL RUN) ---")
        self.session_state["raw_log"] = pipeline_input.raw_log
        self.session_state["enable_self_correction"] = pipeline_input.enable_self_correction

        router = self.agent_factory.get_router_agent(self.model)
        routing_response = await router.arun(message=pipeline_input.raw_log)
        self.llm_logger.log_response(routing_response)

        if not isinstance(routing_response.content, RoutingDecision):
            return {"error": "Router agent failed to produce a valid RoutingDecision."}

        self.session_state["category"] = routing_response.content.failure_category
        self.session_state["snippets"] = "\n".join(routing_response.content.relevant_log_snippets)

        followup_prompt = (
            f"The failure is classified as {self.session_state['category']}. "
            f"Based on the log provided, produce a detailed diagnosis report.\n\n"
            f"Relevant Log Snippets:\n{self.session_state['snippets']}"
        )
        followup_input = FollowupInput(
            user_input=followup_prompt,
            short_term_history=pipeline_input.short_term_history,
            long_term_memory=pipeline_input.long_term_memory
        )
        return await self.run_followup(followup_input)

    def _construct_retry_prompt(self, base_task: str, latest_feedback: str) -> str:
        """
        Reconstructs the prompt to prevent cumulative bloating while 
        preserving full context for response quality.
        """
        return (
            f"{base_task}\n\n"
            f"### REQUIRED IMPROVEMENTS FROM PREVIOUS ATTEMPT:\n"
            f"{latest_feedback}"
        )

    async def run_followup(self, followup_input: FollowupInput) -> Any:
        logger.info("--- STANDARD DIAGNOSIS PIPELINE (FOLLOW-UP) ---")
        if "category" not in self.session_state or "raw_log" not in self.session_state:
            return {"error": "Initial analysis has not been run completely."}

        category = self.session_state["category"]
        raw_log = self.session_state["raw_log"]
        enable_self_correction = self.session_state.get("enable_self_correction", True)

        specialist = self.agent_factory.get_specialist_agent(category, self.model)

        # Store the base prompt to use as a template for retries
        base_prompt_for_specialist = f"Full Log for context:\n{raw_log}\n\nUser Question:\n{followup_input.user_input}"

        diagnosis_prompt = self._construct_prompt_with_memory(
            base_prompt=base_prompt_for_specialist,
            short_term_history=followup_input.short_term_history,
            long_term_memory=followup_input.long_term_memory
        )

        if not enable_self_correction:
            response = await specialist.arun(message=diagnosis_prompt)
            self.llm_logger.log_response(response)
            return response.content

        critic = self.agent_factory.get_critic_agent(self.model)
        
        # Apply structured prompt reconstruction to the self-correction loop
        # This prevents '+= feedback' bloating and satisfies context requirements
        chained_pipeline = specialist + critic
        return await chained_pipeline.arun(
            diagnosis_prompt, 
            self.llm_logger,
            prompt_reconstructor=self._construct_retry_prompt,
            base_task=diagnosis_prompt
        )
