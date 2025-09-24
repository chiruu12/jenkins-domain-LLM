import os
import sys
from typing import Dict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .base import BaseCommand
from data_models import OperatingMode

console = Console()


class HelpCommand(BaseCommand):
    def __init__(self):
        super().__init__("help", "Displays this comprehensive help message.")

    async def execute(self, session) -> None:
        console.print(Panel(
            "The Jenkins AI Agent is a multi-purpose CLI tool. It can run in a log-based mode for analysis or an interactive mode for chat-based debugging and learning. In interactive modes, you can use the slash commands listed below at any time.",
            title="[bold cyan]Usage Overview[/bold cyan]"
        ))

        mode_table = Table(title="[bold green]Operating Modes[/bold green]")
        mode_table.add_column("Mode", style="cyan")
        mode_table.add_column("Description", style="magenta")

        for mode in OperatingMode:
            mode_table.add_row(mode.value, mode.description)

        console.print(mode_table)

        command_table = Table(title="[bold yellow]Available Commands[/bold yellow]")
        command_table.add_column("Command", style="cyan")
        command_table.add_column("Description", style="magenta")
        for name, command in sorted(session.command_handler.commands.items()):
            command_table.add_row(f"/{name}", command.description)

        console.print(command_table)



class OptionsCommand(BaseCommand):
    def __init__(self):
        super().__init__("options", "Configure session settings or save new defaults.")

    async def execute(self, session) -> None:
        choices = [
            "Configure Current Session",
            "Save Current Settings as Global Default",
            "View Current Settings",
            "Cancel",
        ]
        selection = await session._prompt_for_choice("Options Menu", choices, "Cancel")

        if selection == "Configure Current Session":
            await session._configure_session_settings()
        elif selection == "Save Current Settings as Global Default":
            await session._save_defaults_to_config()
        elif selection == "View Current Settings":
            await session._handle_status()


class HistoryCommand(BaseCommand):
    def __init__(self):
        super().__init__("history", "List past sessions.")

    async def execute(self, session) -> None:
        await session._handle_history()


class ViewCommand(BaseCommand):
    def __init__(self):
        super().__init__("view", "View a specific past session. Usage: /view <number>")

    async def execute(self, session) -> None:
        await session._handle_view(session.last_user_input)


class LogsCommand(BaseCommand):
    def __init__(self):
        super().__init__("logs", "Display raw LLM logs for the current session.")

    async def execute(self, session) -> None:
        await session._handle_logs()


class StatusCommand(BaseCommand):
    def __init__(self):
        super().__init__("status", "Display the status of the current session.")

    async def execute(self, session) -> None:
        await session._handle_status()


class ClearCommand(BaseCommand):
    def __init__(self):
        super().__init__("clear", "Clear the terminal screen.")

    async def execute(self, session) -> None:
        os.system('cls' if os.name == 'nt' else 'clear')


class QuitCommand(BaseCommand):
    def __init__(self):
        super().__init__("quit", "Exit the application.")

    async def execute(self, session) -> None:
        console.print("[bold red]Exiting session.[/bold red]")
        sys.exit(0)


class CommandHandler:
    def __init__(self):
        self.commands: Dict[str, BaseCommand] = {}
        self._register_commands()

    def _register_commands(self):
        commands_to_register = [
            HelpCommand(), OptionsCommand(), HistoryCommand(), ViewCommand(),
            LogsCommand(), StatusCommand(), ClearCommand(), QuitCommand(),
        ]
        for cmd in commands_to_register:
            self.commands[cmd.name] = cmd
        self.commands["exit"] = self.commands["quit"]

    async def handle(self, user_input: str, session) -> bool:
        if not user_input.startswith('/'):
            return False

        command_name = user_input[1:].split(" ")[0].lower()
        command = self.commands.get(command_name)

        if command:
            await command.execute(session)
        else:
            console.print("[yellow]Unknown command. Type '/help' for a list of available commands.[/yellow]")

        return True
