import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from data_models import (
    OperatingMode,
    SessionLog,
    AgentExecutionRecord,
    UserInteractionRecord
)

class MemoryManager:
    def __init__(self, runs_dir: Path, run_id: str):
        self.run_dir = runs_dir / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.run_dir / "session.json"
        self.log: Optional[SessionLog] = None

    def start_session(self, mode: OperatingMode, initial_input: str):
        self.log = SessionLog(
            run_id=self.run_dir.name,
            mode=mode,
            initial_input=initial_input
        )

    def log_agent_exchange(self, record: AgentExecutionRecord):
        if not self.log:
            raise RuntimeError("Session not started. Call start_session() first.")
        self.log.session_flow.append(record)

    def log_user_exchange(self, user_input: str):
        if not self.log:
            raise RuntimeError("Session not started. Call start_session() first.")
        record = UserInteractionRecord(user_input=user_input)
        self.log.session_flow.append(record)

    def save(self):
        if self.log:
            with open(self.session_file, "w", encoding="utf-8") as f:
                f.write(self.log.model_dump_json(indent=2))

    @staticmethod
    def list_runs(runs_dir: Path) -> List[str]:
        if not runs_dir.exists():
            return []
        return sorted(
            [d.name for d in runs_dir.iterdir() if d.is_dir() and (d / "session.json").exists()],
            reverse=True
        )

    @staticmethod
    def load_run(runs_dir: Path, run_id: str) -> Optional[SessionLog]:
        session_file = runs_dir / run_id / "session.json"
        if session_file.exists():
            data = json.loads(session_file.read_text(encoding="utf-8"))
            return SessionLog(**data)
        return None
