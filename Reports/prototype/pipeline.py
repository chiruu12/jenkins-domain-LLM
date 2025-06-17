from sanitizer import LogSanitizer
from agents import (
    router_agent,
    config_error_agent,
    test_failure_agent,
    dependency_error_agent,
    infra_failure_agent,
    default_agent,
    critic_agent
)


def run_diagnosis_pipeline(raw_log: str, workspace_path: str, enable_self_correction: bool):
    print("--- PIPELINE START ---")

    log_sanitizer = LogSanitizer()
    cleaned_log = log_sanitizer.run(raw_log)
    print(f"STEP 1: Log Sanitization Complete.\nCleaned Log:\n{cleaned_log}\n")

    routing_decision = router_agent.run(message=cleaned_log)
    failure_category = routing_decision.content.failure_category
    print(f"STEP 2: Routing Complete. Category: {failure_category}\n")

    agent_selection_map = {
        "CONFIGURATION_ERROR": config_error_agent,
        "TEST_FAILURE": test_failure_agent,
        "DEPENDENCY_ERROR": dependency_error_agent,
        "INFRA_FAILURE": infra_failure_agent,
    }

    specialist_agent = agent_selection_map.get(failure_category, default_agent)
    print(f"STEP 3: Specialist Agent Selected: {specialist_agent.description}\n")

    for tool in specialist_agent.tools:
        if hasattr(tool, 'base_path'):
            tool.base_path = workspace_path

    diagnosis_prompt = f"Logs:\n{cleaned_log}\n Investigate and report."

    if not enable_self_correction:
        print("STEP 4: Single-Pass Diagnosis Running...\n")
        final_report = specialist_agent.run(message=diagnosis_prompt)
        return final_report.content.response

    print("STEP 4: Self-Correction Loop Initialized.\n")
    max_retries = 2
    draft_report = None

    for attempt in range(max_retries):
        print(f"--- LOOP ATTEMPT {attempt + 1}/{max_retries} ---")

        draft_report = specialist_agent.run(message=diagnosis_prompt)
        print(f"DRAFT :\n{draft_report.content.response}\n")

        critique_report = critic_agent.run(message=draft_report.content.response)
        print(f"CRITIC's review: Approved={critique_report.content.is_approved}, Feedback='{critique_report.content.critique}'\n")

        if critique_report.content.is_approved:
            print("--- LOOP END: Report Approved ---")
            return draft_report.content.response
        else:
            diagnosis_prompt += f"\n\nA previous attempt was critiqued: '{critique_report.content.critique}'. Please generate an improved report."

    print("--- LOOP END: Max retries reached ---")
    if draft_report is None:
        raise RuntimeError("No valid report was generated after maximum retries.")
    return draft_report.content.response
