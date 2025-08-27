import logging
from pipelines.base import BasePipeline

logger = logging.getLogger(__name__)


class StandardPipeline(BasePipeline):
    """
    Executes the full, multi-step diagnosis workflow:
    1. Routes the failure to a category.
    2. A specialist agent drafts a diagnosis.
    3. A critic agent reviews the diagnosis.
    4. If rejected, the specialist retries with the critic's feedback.
    """

    async def run(self, raw_log: str, enable_self_correction: bool = True) -> str:
        logger.info("--- STANDARD DIAGNOSIS PIPELINE START ---")

        router = self.agent_factory.get_router_agent(self.model)
        routing_response = await router.arun(message=raw_log)
        self.llm_logger.log_response(routing_response)

        category = routing_response.content.failure_category
        snippets = "\n".join(routing_response.content.relevant_log_snippets)
        logger.info(f"Routing complete. Category: {category}")

        specialist = self.agent_factory.get_specialist_agent(category, self.model)
        diagnosis_prompt = f"The failure is classified as {category}. Investigate using the logs and workspace.\nSnippets:\n{snippets}"

        if not enable_self_correction:
            final_report_response = await specialist.arun(message=diagnosis_prompt)
            self.llm_logger.log_response(final_report_response)
            return final_report_response.content.model_dump_json(indent=2)

        last_report = None
        max_retries = 2
        for attempt in range(max_retries):
            logger.info(f"Diagnosis attempt {attempt + 1}/{max_retries}...")
            draft_response = await specialist.arun(message=diagnosis_prompt)
            self.llm_logger.log_response(draft_response)
            last_report = draft_response.content

            critic = self.agent_factory.get_critic_agent(self.model)
            critique_prompt = f"Please review this diagnosis report:\n\n{last_report.model_dump_json()}"
            critique_response = await critic.arun(message=critique_prompt)
            self.llm_logger.log_response(critique_response)

            critique = critique_response.content
            logger.info(f"Critic review: Approved={critique.is_approved}, Feedback='{critique.critique}'")

            if critique.is_approved:
                break
            else:
                feedback = f"\n\nA previous attempt was critiqued: '{critique.critique}'. Address this and generate an improved report."
                diagnosis_prompt += feedback

        return last_report.model_dump_json(indent=2) if last_report else "{}"
