import logging
from typing import Any
from rich.console import Console
from pipelines.base import BasePipeline
from data_models import InteractiveClarification, CritiqueReport

logger = logging.getLogger(__name__)
console = Console()


class InteractivePipeline(BasePipeline):
    async def run(self, user_input: str, initial_context: str) -> Any:
        logger.info("--- INTERACTIVE DEBUGGING PIPELINE START ---")

        conversation_history = []
        if initial_context:
            conversation_history.append(f"Initial Log Context:\n{initial_context}")
        conversation_history.append(f"User Input: {user_input}")

        full_prompt = "\n---\n".join(conversation_history)

        debugger = self.agent_factory.get_interactive_agent(self.model)
        critic = self.agent_factory.get_interactive_critic(self.model)

        last_clarification = None
        max_retries = 2

        for attempt in range(max_retries):
            logger.info(f"Interactive attempt {attempt + 1}/{max_retries}...")
            draft_response = await debugger.arun(message=full_prompt)
            self.llm_logger.log_response(draft_response)

            if not isinstance(draft_response.content, InteractiveClarification):
                logger.error(f"Interactive agent failed on attempt {attempt + 1}. Retrying.")
                feedback = "\n\nCRITICAL FEEDBACK: Your last response was not a valid question. You must ask a question to the user."
                full_prompt += feedback
                continue

            last_clarification = draft_response.content
            critique_prompt = f"Review this interactive question:\n\n{last_clarification.model_dump_json()}"
            critique_response = await critic.arun(message=critique_prompt)
            self.llm_logger.log_response(critique_response)

            if not isinstance(critique_response.content, CritiqueReport):
                logger.warning("Interactive critic failed to produce valid critique. Assuming approval.")
                break

            critique = critique_response.content
            logger.info(f"Interactive Critic review: Approved={critique.is_approved}, Feedback='{critique.critique}'")

            if critique.is_approved:
                break
            else:
                feedback = f"\n\nCRITICAL FEEDBACK: Your last attempt to ask a question was flawed: '{critique.critique}'. Ask a better question."
                full_prompt += feedback

        if last_clarification:
            return last_clarification
        else:
            return {"error": "Failed to generate a valid interactive response after multiple retries."}
