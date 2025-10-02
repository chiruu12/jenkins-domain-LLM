import asyncio
import json
import os
import sys
import shutil
from typing import Dict, Optional, List, Any
import typer
import yaml
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.padding import Padding
from rich.prompt import Prompt, Confirm
from agno.models.base import Model
from agents import AgentFactory
from data_models import (
    OperatingMode, AgentExecutionRecord, SessionSettings, DiagnosisReport,
    QuickSummaryReport, LearningReport, InteractiveClarification, CritiqueReport,
    InitialLogInput, InitialInteractiveInput, FollowupInput
)
from log_manager import LLMInteractionLogger, setup_application_logger
from memory import ConversationMemoryManager, SessionJsonLogger
from models import create_provider
from pipeline import create_pipeline
from sanitizer import ContentSanitizer, CredentialMapper
from settings import settings, CONFIG_PATH
from tools import KnowledgeBaseTools, JenkinsWorkspaceTools, LogAccessTools
from tools.knowledge_base import CoreLightRAGManager
from commands.handlers import CommandHandler

os.environ["TOKENIZERS_PARALLELISM"] = "false"
console = Console()
app = typer.Typer(name="jenkins-agent", help="An AI-powered CLI tool to diagnose Jenkins issues.", no_args_is_help=True)

JENKINS_LOGO = """
[blue]
      ██╗███████╗███╗   ██╗██╗  ██╗██╗███╗   ██╗███████╗
      ██║██╔════╝████╗  ██║██║ ██╔╝██║████╗  ██║██╔════╝
      ██║█████╗  ██╔██╗ ██║█████╔╝ ██║██╔██╗ ██║███████╗
 ██   ██║██╔══╝  ██║╚██╗██║██╔═██╗ ██║██║╚██╗██║╚════██║
 ╚█████╔╝███████╗██║ ╚████║██║  ██╗██║██║ ╚████║███████║
  ╚════╝ ╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝╚══════╝
[/blue]
"""


class CLISession:
    def __init__(self):
        self.app_dir = Path("agent_workspace")
        self.runs_dir = self.app_dir / "runs"
        self.logs_dir = self.app_dir / "logs"
        self.run_id = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        self.run_dir = self.runs_dir / self.run_id
        for d in [self.app_dir, self.runs_dir, self.logs_dir, self.run_dir]:
            d.mkdir(parents=True, exist_ok=True)
        setup_application_logger(self.logs_dir, self.run_id)
        self.session_logger = SessionJsonLogger(self.runs_dir, self.run_id)
        self.conversation_memory: Optional[ConversationMemoryManager] = None
        self.llm_logger = LLMInteractionLogger(self.logs_dir, self.run_id)
        self.sanitizer = ContentSanitizer()
        self.mapper = CredentialMapper()
        self.log_access_tools: Optional[LogAccessTools] = None
        self.jenkins_workspace_tools: Optional[JenkinsWorkspaceTools] = None
        self.knowledge_base_tools: Optional[KnowledgeBaseTools] = None
        self.session_settings: SessionSettings = SessionSettings(**settings.defaults.model_dump())
        self.history_map: Dict[int, str] = {}
        self.command_handler = CommandHandler()
        self.last_user_input: str = ""
        self.selected_mode: Optional[OperatingMode] = None

    async def _prompt_str(self, text: str, **kwargs) -> str:
        while True:
            response = await asyncio.to_thread(Prompt.ask, text, **kwargs)
            self.last_user_input = response
            if response.lower().strip() in ["quit", "exit"]:
                console.print("[bold red]Exiting session.[/bold red]")
                sys.exit(0)
            is_command = await self.command_handler.handle(response, self)
            if not is_command:
                return response

    def _get_active_model(self) -> Model:
        provider = create_provider(self.session_settings.provider)
        return provider.get_chat_model(model_id=self.session_settings.chat_model)

    @staticmethod
    async def _prompt_bool(text: str, **kwargs) -> bool:
        return await asyncio.to_thread(Confirm.ask, text, **kwargs)

    async def _prompt_for_choice(self, text: str, choices: List[str], default: str) -> str:
        console.print(f"[bold yellow]{text}[/bold yellow]")
        choice_map = {str(i + 1): choice for i, choice in enumerate(choices)}
        for i, choice in enumerate(choices, 1):
            is_default = " (default)" if choice == default else ""
            console.print(f"  [cyan]{i}[/cyan]: {choice}{is_default}")
        while True:
            raw_input = await self._prompt_str(">", default=default)
            if raw_input in choice_map:
                return choice_map[raw_input]
            if raw_input.lower() in [c.lower() for c in choices]:
                return next(c for c in choices if c.lower() == raw_input.lower())
            console.print("[red]Invalid selection. Please try again.[/red]")

    async def _prompt_for_path(self, text: str, is_dir: bool = False) -> Optional[Path]:
        console.print(f"[dim]Current directory: {os.getcwd()}[/dim]")
        while True:
            path_str = await self._prompt_str(f"[bold yellow]{text}[/bold yellow]")
            if not path_str: return None
            path = Path(path_str).expanduser()
            if (is_dir and path.exists() and path.is_dir()) or \
                    (not is_dir and path.exists() and path.is_file()):
                return path
            console.print(f"[red]Error: {'Directory' if is_dir else 'File'} not found at '{path_str}'.[/red]")

    async def _configure_session_settings(self):
        console.print(Panel("This wizard will configure the settings for the CURRENT session.",
                            title="[bold]Session Configuration[/bold]", style="yellow"))
        self.session_settings.provider = await self._prompt_for_choice("Select Chat Provider",
                                                                       list(settings.providers.keys()),
                                                                       self.session_settings.provider)
        self.session_settings.chat_model = await self._prompt_str("Enter Chat Model ID",
                                                                  default=self.session_settings.chat_model)
        if await self._prompt_bool("Enable and configure RAG reranker?", default=self.session_settings.use_reranker):
            self.session_settings.use_reranker = True
            reranker_providers = list(settings.providers.keys()) + ["None"]
            self.session_settings.reranker_provider = await self._prompt_for_choice("Select Reranker Provider",
                                                                                    reranker_providers,
                                                                                    self.session_settings.reranker_provider or "None")
            if self.session_settings.reranker_provider != "None":
                self.session_settings.reranker_model = await self._prompt_str("Enter Reranker Model ID")
            else:
                self.session_settings.reranker_provider = None
                self.session_settings.use_reranker = False
        else:
            self.session_settings.use_reranker = False
            self.session_settings.reranker_provider = None
            self.session_settings.reranker_model = None
        console.print(Panel("Session settings have been updated.", style="green"))

    async def _save_defaults_to_config(self):
        with open(CONFIG_PATH, 'r') as f:
            config_data = yaml.safe_load(f)
        config_data['defaults'] = self.session_settings.model_dump()
        with open(CONFIG_PATH, 'w') as f:
            yaml.dump(config_data, f, sort_keys=False)
        console.print(Panel("Current session settings have been saved as the new global defaults.", style="green"))

    async def initialize(self):
        with console.status("[bold green]Initializing backend services...[/bold green]"):
            memory_embedding_provider = create_provider(settings.memory_settings.embedding_provider)
            memory_embedding_func = memory_embedding_provider.get_embedding_function(
                model_id=settings.memory_settings.embedding_model,
                task_type=settings.memory_settings.task_type
            )
            self.conversation_memory = ConversationMemoryManager(embedding_func=memory_embedding_func)
            await self.conversation_memory.initialize()
            rag_provider = create_provider(settings.rag_settings.llm_provider)
            rag_llm_func = rag_provider.get_llm_model_func(model_id=settings.rag_settings.llm_model)
            embedding_provider = create_provider(settings.rag_settings.embedding_provider)
            embedding_func = embedding_provider.get_embedding_function(
                model_id=settings.rag_settings.embedding_model, task_type=settings.rag_settings.task_type
            )
            reranker_func = None
            if self.session_settings.use_reranker and self.session_settings.reranker_provider:
                reranker_provider = create_provider(self.session_settings.reranker_provider)
                reranker_func = reranker_provider.get_reranker_model(model_id=self.session_settings.reranker_model)
            rag_manager = CoreLightRAGManager(working_dir=str(self.run_dir / "rag_workspace"), llm_func=rag_llm_func,
                                              embedding_func=embedding_func, reranker_func=reranker_func)
            await rag_manager.initialize()
            self.log_access_tools = LogAccessTools()
            self.jenkins_workspace_tools = JenkinsWorkspaceTools(str(self.run_dir), self.sanitizer, self.mapper)
            self.knowledge_base_tools = KnowledgeBaseTools(rag_manager)

    @staticmethod
    def _render_diagnosis_report(data: DiagnosisReport) -> Panel:
        md_content = f"### Root Cause\n{data.root_cause}\n\n"
        if data.evidence:
            md_content += "### Evidence\n"
            for title, evidence_text in data.evidence.items():
                md_content += f"**{title}:**\n```\n{evidence_text}\n```\n"
        if data.suggested_fix:
            md_content += "\n### Suggested Fix\n"
            for i, step in enumerate(data.suggested_fix, 1):
                md_content += f"{i}. {step}\n"
        md_content += f"\n---\n*Confidence: **{data.confidence.title()}***"
        return Panel(Markdown(md_content), title="[bold green]Diagnosis Report[/bold green]", border_style="green")

    @staticmethod
    def _render_quick_summary(data: QuickSummaryReport) -> Panel:
        md_content = f"{data.summary}\n\n---\n*Confidence: **{data.confidence.title()}***"
        return Panel(Markdown(md_content), title="[bold green]Quick Summary[/bold green]", border_style="green")

    @staticmethod
    def _render_learning_report(data: LearningReport) -> Panel:
        md_content = f"### Concept Explanation\n{data.concept_explanation}\n\n"
        if data.documentation_links:
            md_content += "### Further Reading\n"
            for link in data.documentation_links:
                md_content += f"- {link}\n"
        return Panel(Markdown(md_content), title="[bold green]Learning Report[/bold green]", border_style="green")

    @staticmethod
    def _render_interactive_clarification(data: InteractiveClarification) -> Panel:
        md_content = f"### Question\n**{data.question}**\n\n"
        if data.suggested_actions:
            md_content += "### Suggested Actions\n"
            for action in data.suggested_actions:
                md_content += f"- {action}\n"
        return Panel(Markdown(md_content), title="[bold cyan]Agent Question[/bold cyan]", border_style="cyan")

    def display_report(self, report: Any):
        try:
            report_obj = report
            if isinstance(report, str):
                try:
                    report_obj = self._reconstruct_model(json.loads(report))
                except json.JSONDecodeError:
                    console.print(
                        Panel(report, title="[bold yellow]Agent Message[/bold yellow]", border_style="yellow"))
                    return
            if isinstance(report_obj, dict) and "error" in report_obj:
                details = report_obj.get("details", "No additional details provided.")
                console.print(Panel(
                    f"[bold]An error occurred:[/bold]\n[red]{report_obj['error']}[/red]\n\n[dim]Details: {details}[/dim]",
                    title="[bold red]Pipeline Error[/bold red]"))
                return
            panel_renderers = {
                DiagnosisReport: self._render_diagnosis_report,
                QuickSummaryReport: self._render_quick_summary,
                LearningReport: self._render_learning_report,
                InteractiveClarification: self._render_interactive_clarification,
            }
            renderer = panel_renderers.get(type(report_obj))
            if renderer:
                panel = renderer(report_obj)
            else:
                pretty_json = json.dumps(report_obj.model_dump() if hasattr(report_obj, 'model_dump') else report_obj,
                                         indent=2, default=str)
                panel = Panel(pretty_json, title="[bold yellow]Raw Agent Response[/bold yellow]", border_style="yellow")
            console.print(panel)
        except Exception as e:
            console.print(Panel(f"A critical error occurred while displaying the report: {e}\n\nRaw Data:\n{report}",
                                title="[bold red]Display Engine Error[/bold red]"))

    async def _handle_history(self):
        runs = self.session_logger.list_runs(self.runs_dir)
        if not runs:
            console.print("[yellow]No past sessions found.[/yellow]")
            return
        self.history_map = {i + 1: run_id for i, run_id in enumerate(runs)}
        console.print(Panel("Past Sessions", style="cyan"))
        for i, run_id in self.history_map.items():
            console.print(f"  [bold cyan]{i}[/bold cyan]: {run_id}")

    async def _handle_view(self, user_input: str):
        parts = user_input.split(" ")
        index_to_view = None
        if len(parts) > 1:
            try:
                index_to_view = int(parts[1])
            except ValueError:
                console.print("[bold red]Invalid command. Usage: /view <number>[/bold red]")
                return
        if index_to_view is None:
            await self._handle_history()
            if not self.history_map: return
            try:
                index_to_view = int(await self._prompt_str("Enter the number of the session to view"))
            except ValueError:
                console.print("[bold red]Invalid input. Please enter a number.[/bold red]")
                return
        run_id = self.history_map.get(index_to_view)
        if not run_id:
            console.print(f"[bold red]Error: Invalid history number '{index_to_view}'.[/bold red]")
            return
        session_log = self.session_logger.load_run(self.runs_dir, run_id)
        if not session_log:
            console.print(f"[bold red]Error: Could not load session {run_id}.[/bold red]")
            return
        console.print(Panel(f"Viewing Session: {run_id}", style="cyan"))
        for turn in session_log.session_flow:
            if isinstance(turn, AgentExecutionRecord):
                console.print(f"\n[bold cyan]Agent ({turn.agent_id}):[/bold cyan]")
                self.display_report(self._reconstruct_model(turn.parsed_response))
            else:
                console.print(f"\n[bold yellow]User:[/bold yellow] {turn.user_input}")

    @staticmethod
    def _reconstruct_model(data: dict) -> Any:
        model_map = {
            ("root_cause", "evidence"): DiagnosisReport,
            ("summary", "confidence"): QuickSummaryReport,
            ("concept_explanation",): LearningReport,
            ("question",): InteractiveClarification,
            ("is_approved", "critique"): CritiqueReport,
        }
        for keys, model_class in model_map.items():
            if all(key in data for key in keys):
                return model_class(**data)
        return data

    async def _handle_logs(self):
        log_file = self.logs_dir / f"llm_{self.run_id}.log"
        if log_file.exists():
            console.print(
                Panel(log_file.read_text(), title=f"LLM Logs for Session {self.run_id}", border_style="yellow"))
        else:
            console.print("[yellow]No LLM logs recorded for this session yet.[/yellow]")

    async def _handle_status(self):
        console.print(Panel(f"Run ID: [cyan]{self.run_id}[/cyan]\n"
                            f"Operating Mode: [cyan]{self.selected_mode.value if self.selected_mode else 'Not Selected'}[/cyan]\n"
                            f"Chat Provider: [cyan]{self.session_settings.provider}[/cyan]\n"
                            f"Chat Model: [cyan]{self.session_settings.chat_model}[/cyan]\n"
                            f"Token Usage: [cyan]{self.llm_logger.get_summary()}[/cyan]",
                            title="[bold]Current Session Status[/bold]"))

    async def _session_loop(self, pipeline):
        is_first_turn = True
        self.session_logger.start_session(self.selected_mode, "")

        while True:
            console.print(Panel(f"Mode: {self.selected_mode.value}", style="dim"))

            try:
                user_query = ""
                memory_query = ""
                raw_log_content = None
                enable_correction = True

                if is_first_turn:
                    if self.selected_mode in [OperatingMode.STANDARD, OperatingMode.QUICK_SUMMARY]:
                        log_file_path = await self._prompt_for_path("Enter path to Jenkins build log")
                        if not log_file_path: return

                        workspace_path = await self._prompt_for_path("Enter path to build workspace (optional)",
                                                                     is_dir=True)
                        if workspace_path:
                            shutil.copytree(workspace_path, self.run_dir, dirs_exist_ok=True)

                        raw_log_content = log_file_path.read_text(encoding='utf-8', errors='ignore')
                        user_query = raw_log_content
                        memory_query = f"Analyze Jenkins log: {log_file_path.name}"

                        self.log_access_tools.set_log_contents(sanitized_log=raw_log_content, raw_log=raw_log_content)
                        self.session_logger.log.initial_input = "Log file analysis"

                        enable_correction = await self._prompt_bool("Enable self-correction?", default=True)
                    else:
                        user_query = await self._prompt_str(">", default="")
                        memory_query = user_query
                        self.session_logger.log.initial_input = user_query
                else:
                    user_query = await self._prompt_str(">")
                    memory_query = user_query

                self.session_logger.log_user_exchange(user_query)

                with console.status("[bold green]Agent is processing..."):
                    short_term_history = self.conversation_memory.get_short_term_history(self.run_id)
                    long_term_memory = await self.conversation_memory.retrieve_relevant_turns(memory_query, self.run_id)

                    context = {"short_term_history": short_term_history, "long_term_memory": long_term_memory}

                    if is_first_turn:
                        if self.selected_mode in [OperatingMode.STANDARD, OperatingMode.QUICK_SUMMARY]:
                            pipeline_input = InitialLogInput(raw_log=raw_log_content,
                                                             enable_self_correction=enable_correction, **context)
                        else:
                            pipeline_input = InitialInteractiveInput(user_input=user_query, **context)
                        result_object = await pipeline.run(pipeline_input)
                    else:
                        pipeline_input = FollowupInput(user_input=user_query, **context)
                        result_object = await pipeline.run_followup(pipeline_input)

                rehydrated_result = self.mapper.rehydrate_model(result_object)
                if hasattr(rehydrated_result, 'model_dump'):
                    await self.conversation_memory.add_turn(self.run_id, user_query, rehydrated_result)

                self.display_report(rehydrated_result)
                is_first_turn = False

            except Exception as e:
                console.print(Panel(f"An unexpected error occurred: {e}", title="[bold red]Critical Error[/bold red]",
                                    expand=False))


    async def run(self):
        console.print(Panel(JENKINS_LOGO, border_style="blue"))
        console.print(Panel("Tips: Type 'quit' or 'exit' at any prompt to leave. Type '/help' for a list of commands.",
                            title="Getting Started"))
        await self._handle_status()
        start_choices = ["Start with Default Settings", "Customize Session Settings"]
        start_action = await self._prompt_for_choice("Select an action to continue", start_choices, start_choices[0])
        if start_action == "Customize Session Settings": await self._configure_session_settings()

        await self.initialize()

        mode_choices = [m.value for m in OperatingMode]
        self.selected_mode = OperatingMode(
            await self._prompt_for_choice("Select an operating mode", mode_choices, OperatingMode.STANDARD.value))

        active_model = self._get_active_model()
        tools_dict = {
            "log_access_tools": self.log_access_tools,
            "jenkins_workspace_tools": self.jenkins_workspace_tools,
            "knowledge_base_tools": self.knowledge_base_tools
        }
        agent_factory = AgentFactory(configured_tools=tools_dict)
        pipeline = create_pipeline(
            mode=self.selected_mode, agent_factory=agent_factory, llm_logger=self.llm_logger,
            model=active_model, conversation_memory=self.conversation_memory
        )

        await self._session_loop(pipeline)

        self.session_logger.save()
        summary_panel = Panel(f"[bold yellow]LLM Interaction Summary:[/bold yellow]\n{self.llm_logger.get_summary()}",
                              title="Usage Statistics", border_style="yellow")
        console.print(Padding(summary_panel, (1, 0)))


@app.command()
def main_entry():
    session = CLISession()
    try:
        asyncio.run(session.run())
    except SystemExit:
        pass
    except (KeyboardInterrupt, EOFError):
        console.print("\n\n[bold yellow]Operation cancelled by user.[/bold yellow]")
    finally:
        if session.conversation_memory:
            session.conversation_memory.close()


if __name__ == "__main__":
    app()