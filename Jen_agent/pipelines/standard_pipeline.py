import logging
import json
from .base import BasePipeline
from data_models import RoutingDecision, DiagnosisReport

logger = logging.getLogger("JenkinsAgentApp")


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

        if not isinstance(routing_response.content, RoutingDecision):
            error_msg = "Router agent failed to produce a valid RoutingDecision object."
            logger.error(f"{error_msg} Got type: {type(routing_response.content)}")
            return json.dumps({"error": error_msg, "details": str(routing_response.content)})

        category = routing_response.content.failure_category
        snippets = "\n".join(routing_response.content.relevant_log_snippets)
        logger.info(f"Routing complete. Category: {category}")

        specialist = self.agent_factory.get_specialist_agent(category, self.model)
        diagnosis_prompt = f"The failure is classified as {category}. Investigate using the provided logs and workspace to produce a detailed diagnosis report.\nRelevant Log Snippets:\n{snippets}"

        if not enable_self_correction:
            logger.info("Running in single-pass mode (self-correction disabled).")
            final_report_response = await specialist.arun(message=diagnosis_prompt)
            self.llm_logger.log_response(final_report_response)

            if not isinstance(final_report_response.content, DiagnosisReport):
                error_msg = "Specialist agent failed to produce a valid DiagnosisReport."
                logger.error(f"{error_msg} Got type: {type(final_report_response.content)}")
                return json.dumps({"error": error_msg, "details": str(final_report_response.content)})

            return final_report_response.content.model_dump_json(indent=2)

        logger.info("Running in self-correction mode.")
        critic = self.agent_factory.get_critic_agent(self.model)
        chained_pipeline = specialist + critic
        return await chained_pipeline.arun(diagnosis_prompt, self.llm_logger)
