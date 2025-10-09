import logging
import sqlite3
import json
from pathlib import Path
from typing import Callable, Awaitable, List, Any, Optional
import numpy as np
import faiss
from pydantic import BaseModel
from settings import settings
from data_models import (
    OperatingMode,
    SessionLog,
    AgentExecutionRecord,
    UserInteractionRecord,
    ConversationTurn
)
logger = logging.getLogger(__name__)


class SessionJsonLogger:
    def __init__(self, runs_dir: Path, run_id: str):
        self.run_dir = runs_dir / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.run_dir / "session.json"
        self.log: Optional[SessionLog] = None

    def start_session(self, mode: OperatingMode, initial_input: str):
        self.log = SessionLog(run_id=self.run_dir.name, mode=mode, initial_input=initial_input)

    def log_agent_exchange(self, record: AgentExecutionRecord):
        if not self.log: raise RuntimeError("Session not started.")
        self.log.session_flow.append(record)

    def log_user_exchange(self, user_input: str):
        if not self.log: raise RuntimeError("Session not started.")
        self.log.session_flow.append(UserInteractionRecord(user_input=user_input))

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


class ConversationMemoryManager:
    """
    Manages a persistent, cross-session conversation memory using a hybrid
    SQLite and FAISS backend for both short-term and long-term recall.
    """

    def __init__(self, embedding_func: Callable[[List[str]], Awaitable[np.ndarray]]):
        self.working_dir = Path(settings.memory_settings.working_dir)
        self.working_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.working_dir / "memory.db"
        self.faiss_path = self.working_dir / "faiss.index"
        self.embedding_func = embedding_func
        self.is_initialized = False
        self.faiss_index: Optional[faiss.IndexIDMap] = None
        self.embedding_dim: Optional[int] = None

    def _get_db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def initialize(self):
        if self.is_initialized:
            return

        logger.info(f"Initializing conversation memory at: {self.working_dir}")
        self._init_database_schema()
        await self._load_or_create_faiss_index()
        self.is_initialized = True

    def _init_database_schema(self):
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS conversations
                           (
                               id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                               session_id          TEXT NOT NULL,
                               user_input          TEXT NOT NULL,
                               agent_response_json TEXT NOT NULL,
                               summary             TEXT,
                               embedding           BLOB NOT NULL,
                               importance_score    REAL     DEFAULT 1.0,
                               timestamp           DATETIME DEFAULT CURRENT_TIMESTAMP
                           )
                           """)
            conn.commit()

    async def _get_embedding_dim(self) -> int:
        if self.embedding_dim is None:
            try:
                test_embedding = await self.embedding_func(["test"])
                self.embedding_dim = test_embedding.shape[1]
            except Exception as e:
                logger.error(f"Failed to determine embedding dimension: {e}", exc_info=True)
                raise ValueError("Could not determine embedding dimension from the provider.") from e
        return self.embedding_dim

    async def _load_or_create_faiss_index(self):
        if self.faiss_path.exists():
            logger.info("Loading existing FAISS index from disk.")
            self.faiss_index = faiss.read_index(str(self.faiss_path))
        else:
            logger.info("No FAISS index found. Creating a new one.")
            dim = await self._get_embedding_dim()
            index = faiss.IndexFlatL2(dim)
            self.faiss_index = faiss.IndexIDMap(index)
            await self._rebuild_faiss_from_db()

    async def _rebuild_faiss_from_db(self):
        if not self.faiss_index:
            return
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, embedding FROM conversations")
            rows = cursor.fetchall()
            if not rows: return
            ids = np.array([row["id"] for row in rows])
            embeddings = np.array([np.frombuffer(row["embedding"], dtype=np.float32) for row in rows])
            if embeddings.shape[0] > 0:
                self.faiss_index.add_with_ids(embeddings, ids)
                self._save_faiss_index()

    async def add_turn(self, session_id: str, user_input: str, agent_response: Any):
        if not self.is_initialized: return

        response_dict = agent_response.model_dump() if isinstance(agent_response, BaseModel) else agent_response
        if not isinstance(response_dict, dict): return

        embedding_array = await self.embedding_func([user_input])
        embedding_bytes = embedding_array[0].astype(np.float32).tobytes()
        agent_response_json = json.dumps(response_dict)

        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversations (session_id, user_input, agent_response_json, embedding) VALUES (?, ?, ?, ?)",
                (session_id, user_input, agent_response_json, embedding_bytes)
            )
            conversation_id = cursor.lastrowid
            conn.commit()
            self.faiss_index.add_with_ids(embedding_array.astype(np.float32), np.array([conversation_id]))
            self._save_faiss_index()

    def get_short_term_history(self, session_id: str, limit: int = 5) -> List[ConversationTurn]:
        """
        Retrieves the most recent turns for a specific session ID.

        Args:
            session_id: The ID of the current session.
            limit: The maximum number of recent turns to retrieve.

        Returns:
            A list of conversation turns in chronological order (oldest to newest).
        """
        if not self.is_initialized:
            return []

        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_input, agent_response_json FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit)
            )
            rows = cursor.fetchall()
            return [
                ConversationTurn(user_input=row["user_input"], agent_response=json.loads(row["agent_response_json"]))
                for row in rows][::-1]

    async def retrieve_relevant_turns(self, query: str, session_id: str, top_k: int = 3) -> List[ConversationTurn]:
        """
        Retrieves the most semantically relevant turns from all *past* sessions.

        Args:
            query: The user's new query text.
            session_id: The current session ID, to exclude from the search.
            top_k: The number of turns to retrieve.

        Returns:
            A list of conversation turns.
        """
        if not self.is_initialized or not self.faiss_index or self.faiss_index.ntotal == 0:
            return []

        query_embedding = (await self.embedding_func([query])).astype(np.float32)
        _, ids = self.faiss_index.search(query_embedding, top_k * 2)
        retrieved_ids = [int(i) for i in ids[0] if i != -1]

        if not retrieved_ids:
            return []

        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(retrieved_ids))
            cursor.execute(
                f"SELECT user_input, agent_response_json, session_id FROM conversations WHERE id IN ({placeholders})",
                retrieved_ids
            )
            rows = cursor.fetchall()

        filtered_rows = [row for row in rows if row["session_id"] != session_id][:top_k]
        return [ConversationTurn(user_input=row["user_input"], agent_response=json.loads(row["agent_response_json"]))
                for row in filtered_rows]

    def _save_faiss_index(self):
        logger.debug(f"Saving FAISS index to {self.faiss_path}")
        faiss.write_index(self.faiss_index, str(self.faiss_path))

    def close(self):
        pass
