import logging
import difflib
from sanitizer import LogSanitizer
from log_manager import LLMInteractionLogger
from agents import get_router_agent, get_specialist_agent, get_critic_agent, get_common_tools
from tools.knowledge_base import KnowledgeBaseTools
from tools.log_access import LogAccessTools
from tools.jenkins_workspace import JenkinsWorkspaceTools

logger = logging.getLogger(__name__)


def _get_best_agent_key(decision: str, agent_keys: list[str]) -> str:
    matches = difflib.get_close_matches(decision, agent_keys, n=1, cutoff=0.8)
    if matches:
        return matches[0]
    logger.warning(f"No confident match for '{decision}'. Using fallback 'UNKNOWN'.")
    return "UNKNOWN"


async def run_diagnosis_pipeline(
        raw_log: str,
        workspace_path: str,
        llm_logger: LLMInteractionLogger,
        kb_tool: KnowledgeBaseTools,
        enable_self_correction: bool
) -> str:
    logger.info("--- DIAGNOSIS PIPELINE START ---")

    sanitizer = LogSanitizer()
    cleaned_log = sanitizer.run(raw_log)
    logger.info("STEP 1: Log Sanitization Complete.")

    router_agent = get_router_agent()
    logger.info(f"STEP 2: Routing failure with {router_agent.model.id}...")
    routing_response = await router_agent.arun(message=cleaned_log)
    llm_logger.log_response(routing_response)

    failure_category = routing_response.content.failure_category
    logger.info(f"STEP 2: Routing Complete. Decision: {failure_category}")

    agent_factory_map = {
        "CONFIGURATION_ERROR": "CONFIGURATION_ERROR",
        "TEST_FAILURE": "TEST_FAILURE",
        "DEPENDENCY_ERROR": "DEPENDENCY_ERROR",
        "INFRA_FAILURE": "INFRA_FAILURE",
        "UNKNOWN": "UNKNOWN",
    }
    agent_key = _get_best_agent_key(failure_category, list(agent_factory_map.keys()))

    logger.info("STEP 3: Preparing Specialist Agent and Tools...")
    common_tools = get_common_tools(kb_tool=kb_tool)

    for tool in common_tools:
        if isinstance(tool, JenkinsWorkspaceTools):
            tool.base_path = workspace_path
        if isinstance(tool, LogAccessTools):
            tool.set_log_content(cleaned_log)

    specialist_agent = get_specialist_agent(agent_key, common_tools=common_tools)
    logger.info(f"STEP 3: Specialist Agent '{specialist_agent.description}' selected.")

    diagnosis_prompt = f"The failure has been classified as {agent_key}. Please investigate the following logs and attached workspace files to produce a detailed diagnosis report.\n\nLogs:\n{cleaned_log}"

    if not enable_self_correction:
        logger.info("STEP 4: Single-Pass Diagnosis Running...")
        final_report_response = await specialist_agent.arun(message=diagnosis_prompt)
        llm_logger.log_response(final_report_response)
        logger.info("--- DIAGNOSIS PIPELINE END ---")
        return final_report_response.content.model_dump_json(indent=2)

    logger.info("STEP 4: Self-Correction Loop Initialized.")
    max_retries = 2
    last_report = None

    for attempt in range(max_retries):
        logger.info(f"--- LOOP ATTEMPT {attempt + 1}/{max_retries} ---")

        draft_report_response = await specialist_agent.arun(message=diagnosis_prompt)
        llm_logger.log_response(draft_report_response)
        last_report = draft_report_response.content
        logger.info(f"DRAFT GENERATED (Reason: {last_report.reasoning})")

        critic_agent = get_critic_agent()
        critique_prompt = f"Please review the following diagnosis report:\n\n{last_report.model_dump_json(indent=2)}"
        critique_response = await critic_agent.arun(message=critique_prompt)
        llm_logger.log_response(critique_response)

        critique = critique_response.content
        logger.info(f"CRITIC REVIEW: Approved={critique.is_approved}, Feedback='{critique.critique}'")

        if critique.is_approved:
            logger.info("--- LOOP END: Report Approved ---")
            logger.info("--- DIAGNOSIS PIPELINE END ---")
            return last_report.model_dump_json(indent=2)
        else:
            feedback = f"\n\nA previous attempt was critiqued: '{critique.critique}'. Please address this feedback and generate an improved report."
            diagnosis_prompt += feedback
            logger.info("Report rejected. Retrying with feedback.")

    logger.warning("--- LOOP END: Max retries reached ---")
    logger.info("--- DIAGNOSIS PIPELINE END ---")
    return last_report.model_dump_json(indent=2) if last_report else "Failed to generate a valid report."
