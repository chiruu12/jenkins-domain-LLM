import logging
from pipelines.base import BasePipeline

logger = logging.getLogger(__name__)


class SummaryPipeline(BasePipeline):
    """
    Executes the quick summary workflow with an optional self-correction step.
    1. A summarizer agent drafts a brief root cause analysis.
    2. A critic agent reviews the summary for brevity and correctness.
    3. If rejected, the summarizer retries with the critic's feedback.
    """

    async def run(self, raw_log: str, enable_self_correction: bool = True) -> str:
        logger.info("--- QUICK SUMMARY PIPELINE START ---")

        summarizer = self.agent_factory.get_quick_summary_agent(self.model)
        summary_prompt = raw_log

        if not enable_self_correction:
            summary_response = await summarizer.arun(message=summary_prompt)
            self.llm_logger.log_response(summary_response)
            return summary_response.content.model_dump_json(indent=2)

        last_summary = None
        max_retries = 2
        for attempt in range(max_retries):
            logger.info(f"Summary attempt {attempt + 1}/{max_retries}...")
            draft_response = await summarizer.arun(message=summary_prompt)
            self.llm_logger.log_response(draft_response)
            last_summary = draft_response.content

            critic = self.agent_factory.get_quick_summary_critic(self.model)
            critique_prompt = f"Review this summary report for brevity and format:\n\n{last_summary.model_dump_json()}"
            critique_response = await critic.arun(message=critique_prompt)
            self.llm_logger.log_response(critique_response)

            critique = critique_response.content
            logger.info(f"Summary Critic review: Approved={critique.is_approved}, Feedback='{critique.critique}'")

            if critique.is_approved:
                break
            else:
                feedback = f"\n\nCRITICAL FEEDBACK: {critique.critique}. You MUST adhere to this feedback."
                summary_prompt = raw_log + feedback

        return last_summary.model_dump_json(indent=2) if last_summary else "{}"
