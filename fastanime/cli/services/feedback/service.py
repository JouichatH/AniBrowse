from contextlib import contextmanager
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


class FeedbackService:
    """Centralized manager for user feedback in interactive menus."""

    def __init__(self, icons_enabled: bool = True):
        self.icons_enabled = icons_enabled

    def success(self, message: str, details: Optional[str] = None) -> None:
        """Show a success message with optional details."""
        icon = "✅ " if self.icons_enabled else ""
        main_msg = f"[bold green]{icon}{message}[/bold green]"

        if details:
            console.print(f"{main_msg}\n[dim]{details}[/dim]")
        else:
            console.print(main_msg)

    def error(self, message: str, details: Optional[str] = None) -> None:
        """Show an error message with optional details."""
        icon = "❌ " if self.icons_enabled else ""
        main_msg = f"[bold red]{icon}Error: {message}[/bold red]"

        if details:
            console.print(f"{main_msg}\n[dim]{details}[/dim]")
        else:
            console.print(main_msg)

    def warning(self, message: str, details: Optional[str] = None) -> None:
        """Show a warning message with optional details."""
        icon = "⚠️ " if self.icons_enabled else ""
        main_msg = f"[bold yellow]{icon}Warning: {message}[/bold yellow]"

        if details:
            console.print(f"{main_msg}\n[dim]{details}[/dim]")
        else:
            console.print(main_msg)

    def info(self, message: str, details: Optional[str] = None) -> None:
        """Show an informational message with optional details."""
        icon = "ℹ️ " if self.icons_enabled else ""
        main_msg = f"[bold blue]{icon}{message}[/bold blue]"

        if details:
            console.print(f"{main_msg}\n[dim]{details}[/dim]")
        else:
            console.print(main_msg)

    def notify_operation_result(
        self,
        operation_name: str,
        success: bool,
        success_msg: Optional[str] = None,
        error_msg: Optional[str] = None,
    ) -> None:
        """Notify user of operation result with standardized messaging."""
        if success:
            msg = success_msg or f"{operation_name} completed successfully"
            self.success(msg)
        else:
            msg = error_msg or f"{operation_name} failed"
            self.error(msg)

    @contextmanager
    def loading_operation(
        self,
        message: str,
        success_msg: Optional[str] = None,
        error_msg: Optional[str] = None,
    ):
        """Context manager for operations with loading indicator and result feedback."""
        with Progress(
            SpinnerColumn(),
            TextColumn(f"[cyan]{message}..."),
            transient=True,
            console=console,
        ) as progress:
            progress.add_task("", total=None)
            try:
                yield
                if success_msg:
                    self.success(success_msg)
            except Exception as e:
                error_details = str(e) if str(e) else None
                final_error_msg = error_msg or "Operation failed"
                self.error(final_error_msg, error_details)
                raise

    def pause_for_user(self, message: str = "Press Enter to continue") -> None:
        """Pause execution and wait for user input."""
        icon = "⏸️ " if self.icons_enabled else ""
        click.pause(f"{icon}{message}...")

    def show_detailed_panel(
        self, title: str, content: str, style: str = "blue"
    ) -> None:
        """Show detailed information in a styled panel."""
        console.print(Panel(content, title=title, border_style=style, expand=True))
        self.pause_for_user()
