import asyncio
import json
import shutil
import typer
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.padding import Padding
from rich.prompt import Prompt, Confirm
from rich.traceback import install as install_rich_tracebacks

import config
from pipeline import run_diagnosis_pipeline
from log_manager import setup_application_logger, LLMInteractionLogger
from tools.knowledge_base import CoreLightRAGManager, KnowledgeBaseTools

console = Console()
install_rich_tracebacks(show_locals=True)
app = typer.Typer(
    name="jenkins-diagnoser",
    help="An AI-powered CLI tool to diagnose Jenkins build failures.",
    no_args_is_help=True,
)

async def main():
    console.print(Panel("🚀 [bold blue]Welcome to the Jenkins AI Diagnosis Wizard[/bold blue] 🚀", expand=False))

    while True:
        log_file_str = Prompt.ask("[bold yellow]Please enter the path to the Jenkins build log file[/bold yellow]")
        log_file = Path(log_file_str)
        if log_file.exists() and log_file.is_file():
            break
        console.print(f"[bold red]Error:[/bold red] File not found at '{log_file_str}'. Please try again.")

    workspace_str = Prompt.ask("[bold yellow]Enter path to the build workspace (optional, press Enter to skip)[/bold yellow]", default=None)
    workspace = Path(workspace_str) if workspace_str else None
    if workspace and (not workspace.exists() or not workspace.is_dir()):
        console.print(f"[bold red]Error:[/bold red] Workspace directory not found at '{workspace_str}'.")
        raise typer.Exit(code=1)

    enable_correction = Confirm.ask("[bold yellow]Enable critic agent for self-correction? (Recommended)[/bold yellow]", default=True)

    run_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    run_dir = config.RUNS_DIR / run_timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"\n[dim]Setting up isolated run environment in: [bold]{run_dir}[/bold][/dim]")

    isolated_log_path = run_dir / log_file.name
    shutil.copy(log_file, isolated_log_path)
    if workspace:
        shutil.copytree(workspace, run_dir, dirs_exist_ok=True)

    config.LOGS_DIR.mkdir(exist_ok=True)
    setup_application_logger(config.LOGS_DIR)
    llm_logger = LLMInteractionLogger(config.LOGS_DIR)
    rag_manager = CoreLightRAGManager()
    kb_tool = KnowledgeBaseTools(core_manager=rag_manager)

    try:
        await rag_manager.initialize()
        log_content = isolated_log_path.read_text(encoding="utf-8")

        final_report_json = ""
        with console.status("[bold green]AI agents are analyzing the build...", spinner="dots"):
            final_report_json = await run_diagnosis_pipeline(
                raw_log=log_content,
                workspace_path=str(run_dir),
                llm_logger=llm_logger,
                kb_tool=kb_tool,
                enable_self_correction=enable_correction
            )

        console.line(2)
        console.print(Panel("✅ [bold green]Diagnosis Complete[/bold green]", expand=False))

        report_data = json.loads(final_report_json)
        report_md = f"### 🕵️ Root Cause\n{report_data.get('root_cause', 'N/A')}\n\n###(Evidence)\n"
        for title, evidence in report_data.get('evidence', {}).items():
            report_md += f"**{title}:**\n```\n{evidence}\n```\n"
        report_md += "\n### 💡 Suggested Fix\n"
        for i, step in enumerate(report_data.get('suggested_fix', []), 1):
            report_md += f"{i}. {step}\n"
        report_md += f"\n---\n*Confidence: **{report_data.get('confidence', 'N/A')}***"

        console.print(Panel(Markdown(report_md), title="[bold]Diagnosis Report[/bold]", border_style="cyan"))
        summary_panel = Panel(
            f"[bold yellow]LLM Interaction Summary:[/bold yellow]\n{llm_logger.get_summary()}",
            title="Usage Statistics", border_style="yellow"
        )
        console.print(Padding(summary_panel, (1, 0)))

    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred:[/bold red]")
        console.print_exception(show_locals=True)
    finally:
        if rag_manager.is_initialized:
            await rag_manager.finalize()
            console.print("[dim]Knowledge Base finalized.[/dim]")

@app.callback()
def callback():
    pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        console.print("\n\n[bold yellow]Diagnosis cancelled by user. Exiting.[/bold yellow]")
