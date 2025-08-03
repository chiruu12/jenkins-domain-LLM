from pathlib import Path

DEFAULT_MODEL_ID = "openai/gpt-4.1-mini-2025-04-14"


PROMPTS_DIR = Path("prompts")
WORKSPACE_BASE_DIR = Path("workspace")
LOGS_DIR = Path("logs")
RUNS_DIR = Path("runs")

agent_factory_map = {
        "CONFIGURATION_ERROR": "CONFIGURATION_ERROR",
        "TEST_FAILURE": "TEST_FAILURE",
        "DEPENDENCY_ERROR": "DEPENDENCY_ERROR",
        "INFRA_FAILURE": "INFRA_FAILURE",
        "UNKNOWN": "UNKNOWN",
    }
