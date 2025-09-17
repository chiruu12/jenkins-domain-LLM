import logging
from typing import Any
from pipelines.base import BasePipeline
from data_models import QuickSummaryReport, CritiqueReport

logger = logging.getLogger(__name__)


class SummaryPipeline(BasePipeline):
    async def run(self, raw_log: str, enable_self_correction: bool = True) -> Any:
        logger.info("--- QUICK SUMMARY PIPELINE START ---")

        summarizer = self.agent_factory.get_quick_summary_agent(self.model)
        summary_prompt = raw_log

        if not enable_self_correction:
            summary_response = await summarizer.arun(message=summary_prompt)
            self.llm_logger.log_response(summary_response)
            return summary_response.content

        last_summary = None
        max_retries = 2
        for attempt in range(max_retries):
            logger.info(f"Summary attempt {attempt + 1}/{max_retries}...")
            draft_response = await summarizer.arun(message=summary_prompt)
            self.llm_logger.log_response(draft_response)

            if not isinstance(draft_response.content, QuickSummaryReport):
                logger.error(f"Summarizer failed to produce a valid report on attempt {attempt + 1}. Retrying.")
                feedback = "\n\nCRITICAL FEEDBACK: Your last response was not in the correct format. You MUST respond with a valid object matching the schema."
                summary_prompt += feedback
                continue

            last_summary = draft_response.content
            critic = self.agent_factory.get_quick_summary_critic(self.model)
            critique_prompt = f"Review this summary report for brevity and format:\n\n{last_summary.model_dump_json()}"
            critique_response = await critic.arun(message=critique_prompt)
            self.llm_logger.log_response(critique_response)

            if not isinstance(critique_response.content, CritiqueReport):
                logger.warning("Summary critic failed to produce a valid critique. Assuming approval.")
                break

            critique = critique_response.content
            logger.info(f"Summary Critic review: Approved={critique.is_approved}, Feedback='{critique.critique}'")

            if critique.is_approved:
                break
            else:
                feedback = f"\n\nCRITICAL FEEDBACK: {critique.critique}. You MUST adhere to this feedback."
                summary_prompt = raw_log + feedback

        if last_summary:
            return last_summary
        else:
            return {"error": "Failed to generate a valid summary after multiple retries."}
