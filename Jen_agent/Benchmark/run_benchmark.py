import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv
import os
from tqdm import tqdm
from typing import List, Dict, Any

from agno.agent import Agent
from agno.tools import Toolkit

from models.google.client import GoogleProvider
from models.openai.client import OpenAIChat
from tools.knowledge_base import CoreLightRAGManager
from data_models import BenchmarkCritique


QUESTIONS_FILE = Path("Benchmark/benchmark_data/questions.json")
RESULTS_FILE = Path("Benchmark/benchmark_data/benchmark_results.json")
RAG_KNOWLEDGE_BASE_DIR = Path("./agent_workspace/knowledge_base")

AGENT_UNDER_TEST_MODEL = "gpt-4.1-mini"
CRITIC_MODEL = "gemini-pro-latest"
EMBEDDING_MODEL_ID = "text-embedding-004"
RAG_MODEL_ID = "gemini-2.0-flash"


class RAGTool(Toolkit):
    """A tool that queries the knowledge base and records a history of all calls."""

    def __init__(self, rag_manager: CoreLightRAGManager):
        super().__init__(name="jenkins_knowledge_base")
        self.rag_manager = rag_manager
        self.call_history: List[Dict[str, Any]] = []
        self.register(self.query)

    def reset(self):
        """Clears the history for the next benchmark question."""
        self.call_history = []

    async def query(self, search_query: str) -> str:
        """
        Use this tool to find information about Jenkins. Provide a detailed search_query.
        """
        retrieved_context = await self.rag_manager.query(query_text=search_query)

        # Append a record of this specific call to the history
        self.call_history.append({
            "search_query": search_query,
            "retrieved_context": retrieved_context
        })
        return retrieved_context


CRITIC_PROMPT_TEMPLATE = """
You are a highly intelligent and impartial AI evaluator for a Retrieval-Augmented Generation (RAG) system. Your task is to evaluate an AI agent's answer based on a question, the context the agent retrieved, and the ideal ground truth context.

**EVALUATION CRITERIA:**
1.  **Context Relevance:** Was the "RETRIEVED CONTEXT" relevant to the user's "QUESTION"?
2.  **Context Sufficiency:** Did the "RETRIEVED CONTEXT" contain enough information to fully answer the "QUESTION"?
3.  **Correctness:** Does the "AGENT'S ANSWER" correctly and completely address the "QUESTION"?
4.  **Groundedness:** Is the "AGENT'S ANSWER" fully supported by the information in the "GROUND TRUTH CONTEXT"? The answer MUST NOT contain any information not present in the ground truth.

**INPUT:**

---QUESTION---
{question}

---RETRIEVED CONTEXT---
{retrieved_context}

---GROUND TRUTH CONTEXT---
{ground_truth_context}

---AGENT'S ANSWER---
{agent_answer}

**YOUR TASK:**
Based on all the inputs and the criteria above, provide a structured evaluation of the "AGENT'S ANSWER".
"""


async def main():
    print("--- Starting RAG Benchmark ---")
    load_dotenv()

    if not all([os.getenv("OPENAI_API_KEY"), os.getenv("GOOGLE_API_KEY"), os.getenv("LMSTUDIO_BASE_URL")]):
        print("\n[ERROR] Missing required environment variables.")
        exit(1)

    print("Initializing providers and RAG knowledge base...")
    openai_provider = OpenAIChat(id=AGENT_UNDER_TEST_MODEL, api_key=os.getenv("OPENAI_API_KEY"))
    google_provider = GoogleProvider()
    embedding_func = google_provider.get_embedding_function(EMBEDDING_MODEL_ID)
    llm_func = google_provider.get_llm_model_func(model_id=RAG_MODEL_ID)

    rag_manager = CoreLightRAGManager(
        working_dir=str(RAG_KNOWLEDGE_BASE_DIR),
        embedding_func=embedding_func,
        llm_func=llm_func
    )
    await rag_manager.initialize()
    print("Initialization complete.")


    rag_tool = RAGTool(rag_manager)

    agent_under_test = Agent(
        model=openai_provider,
        tools=[rag_tool],
        instructions=["You are a helpful Jenkins expert. Use your tool to find information."]
    )

    critic_agent = Agent(
        model=google_provider.get_chat_model(model_id=CRITIC_MODEL),
        response_model=BenchmarkCritique,
        instructions=[CRITIC_PROMPT_TEMPLATE]
    )

    if not QUESTIONS_FILE.exists():
        print(f"[ERROR] Questions file not found at '{QUESTIONS_FILE}'.")
        exit(1)
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print(f"Starting benchmark for {len(questions)} questions...")
    results = []
    for item in tqdm(questions, desc="Running Benchmark"):
        question = item["question"]
        ground_truth_context = item["ground_truth_context"]

        rag_tool.reset()

        response = await agent_under_test.arun(message=question)
        agent_answer = str(response.content)

        retrieved_history = rag_tool.call_history

        if retrieved_history:
            full_retrieved_context = "\n\n---\n[NEXT CONTEXT]\n---\n\n".join(
                [call["retrieved_context"] for call in retrieved_history]
            )
        else:
            full_retrieved_context = "Agent did not use the RAG tool."

        critique_prompt = CRITIC_PROMPT_TEMPLATE.format(
            question=question,
            retrieved_context=full_retrieved_context,
            ground_truth_context=ground_truth_context,
            agent_answer=agent_answer
        )
        critique_response = await critic_agent.arun(message=critique_prompt)

        results.append({
            "question_id": item["question_id"],
            "source_file": item["source_file"],
            "question": question,
            "retrieved_tool_calls": retrieved_history,
            "agent_answer": agent_answer,
            "critique": critique_response.content.model_dump() if critique_response.content else None,
        })

    RESULTS_FILE.parent.mkdir(exist_ok=True)
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n✅ Benchmark complete!")
    print(f"Results saved to '{RESULTS_FILE}'")


if __name__ == "__main__":
    asyncio.run(main())
