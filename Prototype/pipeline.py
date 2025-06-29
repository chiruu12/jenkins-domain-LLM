import difflib
import logging
from sanitizer import LogSanitizer
from agents import (
    get_router_agent,
    get_config_error_agent,
    get_test_failure_agent,
    get_dependency_error_agent,
    get_infra_failure_agent,
    get_default_agent,
    get_critic_agent,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def get_best_agent_key(decision: str, agent_keys: list[str], fallback: str) -> str:
    matches = difflib.get_close_matches(decision, agent_keys, n=1, cutoff=0.8)
    if matches:
        best_match = matches[0]
        if best_match != decision:
            logger.info(f"Close match found: '{decision}' -> '{best_match}'.")
        return best_match
    logger.warning(f"No confident match for '{decision}'. Using fallback '{fallback}'.")
    return fallback

def run_diagnosis_pipeline(raw_log: str, workspace_path: str, enable_self_correction: bool):
    """
    Executes the full AI diagnosis pipeline from log sanitization to final report.
    """
    logger.info("--- PIPELINE START ---")

    router_agent = get_router_agent()
    critic_agent = get_critic_agent()

    log_sanitizer = LogSanitizer()
    cleaned_log = log_sanitizer.run(raw_log)
    logger.info("STEP 1: Log Sanitization Complete.")
    logger.debug(f"Cleaned Log:\n{cleaned_log}\n")

    routing_decision = router_agent.run(message=cleaned_log)
    failure_category_decision = routing_decision.content.failure_category
    logger.info(f"STEP 2: Routing Complete. Initial Decision: {failure_category_decision}")

    agent_factory_map = {
        "CONFIGURATION_ERROR": get_config_error_agent,
        "TEST_FAILURE": get_test_failure_agent,
        "DEPENDENCY_ERROR": get_dependency_error_agent,
        "INFRA_FAILURE": get_infra_failure_agent,
        "UNKNOWN": get_default_agent,
    }

    agent_key = get_best_agent_key(
        failure_category_decision,
        list(agent_factory_map.keys()),
        fallback="UNKNOWN"
    )

    specialist_agent_factory = agent_factory_map[agent_key]
    specialist_agent = specialist_agent_factory()
    logger.info(f"STEP 3: Specialist Agent Selected: {specialist_agent.description}")

    for tool in specialist_agent.tools:
        if hasattr(tool, 'base_path'):
            tool.base_path = workspace_path

    diagnosis_prompt = f"Logs:\n{cleaned_log}\n Investigate and report."

    if not enable_self_correction:
        logger.info("STEP 4: Single-Pass Diagnosis Running...")
        final_report = specialist_agent.run(message=diagnosis_prompt)
        return final_report.content.response

    logger.info("STEP 4: Self-Correction Loop Initialized.")
    max_retries = 2
    draft_report = None

    for attempt in range(max_retries):
        logger.info(f"--- LOOP ATTEMPT {attempt + 1}/{max_retries} ---")

        draft_report = specialist_agent.run(message=diagnosis_prompt)
        logger.info(f"DRAFT GENERATED (Reason: {draft_report.content.reason})")
        logger.debug(f"DRAFT CONTENT:\n{draft_report.content.response}")

        critique_report = critic_agent.run(message=draft_report.content.response)
        logger.info(
            f"CRITIC's review: Approved={critique_report.content.is_approved}, Feedback='{critique_report.content.critique}'")

        if critique_report.content.is_approved:
            logger.info("--- LOOP END: Report Approved ---")
            return draft_report.content.response
        else:
            diagnosis_prompt += f"\n\nA previous attempt was critiqued: '{critique_report.content.critique}'. Please generate an improved report."
            logger.info("Report rejected. Retrying with feedback.")

        logger.warning("--- LOOP END: Max retries reached ---")
        if draft_report is None:
            logger.error("No valid report was generated after maximum retries.")
            raise RuntimeError("No valid report was generated after maximum retries.")

        logger.info("Returning last generated draft after max retries.")
        return draft_report.content.response
