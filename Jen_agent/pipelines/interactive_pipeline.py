import logging
from rich.console import Console
from rich.prompt import Prompt
from pipelines.base import BasePipeline

logger = logging.getLogger(__name__)
console = Console()


class InteractivePipeline(BasePipeline):
    """
    Manages a stateful, interactive debugging session with the user.
    Within each turn, it uses a self-correction loop to refine the question it asks.
    """

    async def run(self, initial_context: str) -> str:
        logger.info("--- INTERACTIVE DEBUGGING PIPELINE START ---")

        conversation_history = [f"Initial Log Context:\n{initial_context}"]

        while True:
            full_prompt = "\n---\n".join(conversation_history)

            debugger = self.agent_factory.get_interactive_agent(self.model)
            critic = self.agent_factory.get_interactive_critic(self.model)

            last_clarification = None
            max_retries = 2

            for attempt in range(max_retries):
                with console.status("[bold green]Agent is thinking..."):
                    logger.info(f"Interactive attempt {attempt + 1}/{max_retries}...")
                    draft_response = await debugger.arun(message=full_prompt)
                    self.llm_logger.log_response(draft_response)
                    last_clarification = draft_response.content

                    critique_prompt = f"Review this interactive question:\n\n{last_clarification.model_dump_json()}"
                    critique_response = await critic.arun(message=critique_prompt)
                    self.llm_logger.log_response(critique_response)

                    critique = critique_response.content
                    logger.info(
                        f"Interactive Critic review: Approved={critique.is_approved}, Feedback='{critique.critique}'")

                    if critique.is_approved:
                        break
                    else:
                        feedback = f"\n\nCRITICAL FEEDBACK: Your last attempt to ask a question was flawed: '{critique.critique}'. Ask a better question."
                        full_prompt += feedback

            console.print(f"\n[bold cyan]Agent:[/bold cyan] {last_clarification.question}")
            if last_clarification.suggested_actions:
                console.print("[dim]Suggested next steps:[/dim]")
                for action in last_clarification.suggested_actions:
                    console.print(f"  - {action}")

            user_input = Prompt.ask("\n[bold yellow]Your response (or type 'quit' to exit)[/bold yellow]")

            if user_input.lower().strip() in ["quit", "exit"]:
                console.print("[bold red]Ending interactive session.[/bold red]")
                break

            conversation_history.append(f"User Response: {user_input}")

        return "Interactive session concluded."
