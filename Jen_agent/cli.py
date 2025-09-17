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
    OperatingMode,
    AgentExecutionRecord,
    SessionSettings,
    DiagnosisReport,
    QuickSummaryReport,
    LearningReport,
    InteractiveClarification,
    CritiqueReport
)
from log_manager import LLMInteractionLogger, setup_application_logger
from memory import MemoryManager
from models import create_provider
from pipeline import create_pipeline
from sanitizer import ContentSanitizer, CredentialMapper
from settings import settings, CONFIG_PATH
from tools import KnowledgeBaseTools, JenkinsWorkspaceTools, LogAccessTools
from tools.knowledge_base import CoreLightRAGManager
from commands.handlers import CommandHandler

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

        self.memory_manager = MemoryManager(self.runs_dir, self.run_id)
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
        choice_map = {}
        for i, choice in enumerate(choices, 1):
            is_default = " (default)" if choice == default else ""
            console.print(f"  [cyan]{i}[/cyan]: {choice}{is_default}")
            choice_map[str(i)] = choice

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
            if not path_str:
                return None

            path = Path(path_str).expanduser()

            if is_dir:
                if path.exists() and path.is_dir():
                    return path
                console.print(f"[red]Error: Directory not found at '{path_str}'. Please provide a valid path.[/red]")
            else:
                if path.exists() and path.is_file():
                    return path
                console.print(f"[red]Error: File not found at '{path_str}'. Please provide a valid path.[/red]")

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
            if self.session_settings.reranker_provider == "None":
                self.session_settings.reranker_provider = None
                self.session_settings.use_reranker = False
            else:
                self.session_settings.reranker_model = await self._prompt_str("Enter Reranker Model ID")
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
            rag_provider = create_provider(settings.rag_settings.llm_provider)
            rag_llm_func = rag_provider.get_llm_model_func(model_id=settings.rag_settings.llm_model)

            embedding_provider = create_provider(settings.rag_settings.embedding_provider)
            embedding_func = embedding_provider.get_embedding_function(
                model_id=settings.rag_settings.embedding_model,
                task_type=settings.rag_settings.task_type
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
        """
        A robust method to display any type of agent output in a formatted way.
        It intelligently handles Pydantic models, JSON strings, and error dictionaries.
        """
        try:
            report_obj = report

            if isinstance(report, str):
                try:
                    data = json.loads(report)
                    report_obj = self._reconstruct_model(data)
                except json.JSONDecodeError:
                    console.print(
                        Panel(report, title="[bold yellow]Agent Message[/bold yellow]", border_style="yellow"))
                    return

            if isinstance(report_obj, dict) and "error" in report_obj:
                details = report_obj.get("details", "No additional details provided.")
                console.print(Panel(
                    f"[bold]An error occurred:[/bold]\n[red]{report_obj['error']}[/red]\n\n[dim]Details: {details}[/dim]",
                    title="[bold red]Pipeline Error[/bold red]", border_style="red"
                ))
                return
            if isinstance(report_obj, DiagnosisReport):
                panel = self._render_diagnosis_report(report_obj)
            elif isinstance(report_obj, QuickSummaryReport):
                panel = self._render_quick_summary(report_obj)
            elif isinstance(report_obj, LearningReport):
                panel = self._render_learning_report(report_obj)
            elif isinstance(report_obj, InteractiveClarification):
                panel = self._render_interactive_clarification(report_obj)
            else:
                pretty_json = json.dumps(report_obj, indent=2, default=str)
                panel = Panel(pretty_json, title="[bold yellow]Raw Agent Response[/bold yellow]", border_style="yellow")

            console.print(panel)

        except Exception as e:
            console.print(Panel(f"A critical error occurred while displaying the report: {e}\n\nRaw Data:\n{report}",
                                title="[bold red]Display Engine Error[/bold red]"))

    async def _handle_history(self):
        runs = self.memory_manager.list_runs(self.runs_dir)
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

        session_log = self.memory_manager.load_run(self.runs_dir, run_id)
        if not session_log:
            console.print(f"[bold red]Error: Could not load session {run_id}.[/bold red]")
            return

        console.print(Panel(f"Viewing Session: {run_id}", style="cyan"))
        for turn in session_log.session_flow:
            if isinstance(turn, AgentExecutionRecord):
                console.print(f"\n[bold cyan]Agent ({turn.agent_id}):[/bold cyan]")
                report_obj = self._reconstruct_model(turn.parsed_response)
                self.display_report(report_obj)
            else:
                console.print(f"\n[bold yellow]User:[/bold yellow] {turn.user_input}")

    @staticmethod
    def _reconstruct_model(data: dict) -> Any:
        if "root_cause" in data and "evidence" in data: return DiagnosisReport(**data)
        if "summary" in data and "confidence" in data: return QuickSummaryReport(**data)
        if "concept_explanation" in data: return LearningReport(**data)
        if "question" in data: return InteractiveClarification(**data)
        if "is_approved" in data and "critique" in data: return CritiqueReport(**data)
        return data

    async def _handle_logs(self):
        log_file = self.logs_dir / f"llm_{self.run_id}.log"
        if log_file.exists():
            console.print(
                Panel(log_file.read_text(), title=f"LLM Logs for Session {self.run_id}", border_style="yellow"))
        else:
            console.print("[yellow]No LLM logs recorded for this session yet.[/yellow]")

    async def _handle_status(self):
        console.print(Panel(
            f"Run ID: [cyan]{self.run_id}[/cyan]\n"
            f"Operating Mode: [cyan]{self.selected_mode.value if self.selected_mode else 'Not Selected'}[/cyan]\n"
            f"Chat Provider: [cyan]{self.session_settings.provider}[/cyan]\n"
            f"Chat Model: [cyan]{self.session_settings.chat_model}[/cyan]\n"
            f"Token Usage: [cyan]{self.llm_logger.get_summary()}[/cyan]",
            title="[bold]Current Session Status[/bold]"
        ))

    async def _run_log_based_pipeline(self, mode: OperatingMode, pipeline):
        log_file = await self._prompt_for_path("Enter path to Jenkins build log")
        if not log_file:
            console.print("[bold red]Log file path is required. Aborting.[/bold red]")
            return

        workspace_path = await self._prompt_for_path("Enter path to build workspace (optional, press Enter to skip)",
                                                     is_dir=True)
        if workspace_path:
            shutil.copytree(workspace_path, self.run_dir, dirs_exist_ok=True)
            console.print(f"[dim]Copied workspace contents to secure run directory.[/dim]")

        raw_log = log_file.read_text(encoding='utf-8', errors='ignore')
        sanitized_log = self.sanitizer.sanitize(raw_log, self.mapper)
        self.log_access_tools.set_log_contents(sanitized_log=sanitized_log, raw_log=raw_log)
        self.memory_manager.start_session(mode, raw_log)
        enable_correction = await self._prompt_bool("Enable self-correction critic agent?", default=True)

        try:
            with console.status("[bold green]AI agents are analyzing..."):
                result_object = await pipeline.run(raw_log=sanitized_log, enable_self_correction=enable_correction)

            rehydrated_result = self.mapper.rehydrate_model(result_object)
            self.display_report(rehydrated_result)
        except Exception as e:
            console.print(Panel(f"An unexpected error occurred in the pipeline: {e}",
                                title="[bold red]Pipeline Error[/bold red]"))

    async def _run_interactive_pipeline(self, mode: OperatingMode, pipeline):
        initial_input = ""
        if mode == OperatingMode.INTERACTIVE:
            initial_input = await self._prompt_str("[bold yellow]Provide initial context (optional)[/bold yellow]",
                                                   default="")
        self.memory_manager.start_session(mode, initial_input)

        while True:
            status_bar = f"Mode: {mode.value} | Model: {self.session_settings.provider} -> {self.session_settings.chat_model}"
            console.print(Panel(status_bar, style="dim"))
            user_input = await self._prompt_str(">")
            self.memory_manager.log_user_exchange(user_input)
            try:
                with console.status("[bold green]Agent is processing..."):
                    kwargs = {"initial_context": initial_input,
                              "user_input": user_input} if mode == OperatingMode.INTERACTIVE else {
                        "user_question": user_input}
                    result_object = await pipeline.run(**kwargs)
                    initial_input = ""

                rehydrated_result = self.mapper.rehydrate_model(result_object)
                self.display_report(rehydrated_result)
            except Exception as e:
                console.print(Panel(f"An unexpected error occurred in the pipeline: {e}",
                                    title="[bold red]Pipeline Error[/bold red]"))

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

        pipeline = create_pipeline(self.selected_mode, agent_factory, self.llm_logger, model=active_model)

        if self.selected_mode in [OperatingMode.STANDARD, OperatingMode.QUICK_SUMMARY]:
            await self._run_log_based_pipeline(self.selected_mode, pipeline)
        else:
            await self._run_interactive_pipeline(self.selected_mode, pipeline)

        self.memory_manager.save()
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


if __name__ == "__main__":
    app()
