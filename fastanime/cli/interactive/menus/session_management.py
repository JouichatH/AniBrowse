"""
Session management menu for the interactive CLI.
Provides options to save, load, and manage session state.
"""

from datetime import datetime
from pathlib import Path
from typing import Callable, Dict

from rich.console import Console
from rich.table import Table

from ....core.constants import APP_DIR
from ...utils.feedback import create_feedback_manager
from ..session import Context, session
from ..state import ControlFlow, State

MenuAction = Callable[[], str]


@session.menu
def session_management(ctx: Context, state: State) -> State | ControlFlow:
    """
    Session management menu for saving, loading, and managing session state.
    """
    icons = ctx.config.general.icons
    feedback = create_feedback_manager(icons)
    console = Console()
    console.clear()

    # Show current session stats
    _display_session_info(console, icons)

    options: Dict[str, MenuAction] = {
        f"{'💾 ' if icons else ''}Save Current Session": lambda: _save_session(ctx, feedback),
        f"{'📂 ' if icons else ''}Load Session": lambda: _load_session(ctx, feedback),
        f"{'📋 ' if icons else ''}List Saved Sessions": lambda: _list_sessions(ctx, feedback),
        f"{'🗑️ ' if icons else ''}Cleanup Old Sessions": lambda: _cleanup_sessions(ctx, feedback),
        f"{'💾 ' if icons else ''}Create Manual Backup": lambda: _create_backup(ctx, feedback),
        f"{'⚙️ ' if icons else ''}Session Settings": lambda: _session_settings(ctx, feedback),
        f"{'🔙 ' if icons else ''}Back to Main Menu": lambda: "BACK",
    }

    choice_str = ctx.selector.choose(
        prompt="Select Session Action",
        choices=list(options.keys()),
        header="Session Management",
    )

    if not choice_str:
        return ControlFlow.BACK

    result = options[choice_str]()
    
    if result == "BACK":
        return ControlFlow.BACK
    else:
        return ControlFlow.CONTINUE


def _display_session_info(console: Console, icons: bool):
    """Display current session information."""
    session_stats = session.get_session_stats()
    
    table = Table(title=f"{'📊 ' if icons else ''}Current Session Info")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Current States", str(session_stats["current_states"]))
    table.add_row("Current Menu", session_stats["current_menu"] or "None")
    table.add_row("Auto-Save", "Enabled" if session_stats["auto_save_enabled"] else "Disabled")
    table.add_row("Has Auto-Save", "Yes" if session_stats["has_auto_save"] else "No")
    table.add_row("Has Crash Backup", "Yes" if session_stats["has_crash_backup"] else "No")
    
    console.print(table)
    console.print()


def _save_session(ctx: Context, feedback) -> str:
    """Save the current session."""
    session_name = ctx.selector.ask("Enter session name (optional):")
    description = ctx.selector.ask("Enter session description (optional):")
    
    if not session_name:
        session_name = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    sessions_dir = APP_DIR / "sessions"
    file_path = sessions_dir / f"{session_name}.json"
    
    if file_path.exists():
        if not feedback.confirm(f"Session '{session_name}' already exists. Overwrite?"):
            feedback.info("Save cancelled")
            return "CONTINUE"
    
    success = session.save(file_path, session_name, description or "")
    if success:
        feedback.success(f"Session saved as '{session_name}'")
    
    return "CONTINUE"


def _load_session(ctx: Context, feedback) -> str:
    """Load a saved session."""
    sessions = session.list_saved_sessions()
    
    if not sessions:
        feedback.warning("No saved sessions found")
        return "CONTINUE"
    
    # Create choices with session info
    choices = []
    session_map = {}
    
    for sess in sessions:
        choice_text = f"{sess['name']} - {sess['description'][:50]}{'...' if len(sess['description']) > 50 else ''}"
        choices.append(choice_text)
        session_map[choice_text] = sess
    
    choices.append("Cancel")
    
    choice = ctx.selector.choose(
        "Select session to load:",
        choices=choices,
        header="Available Sessions"
    )
    
    if not choice or choice == "Cancel":
        return "CONTINUE"
    
    selected_session = session_map[choice]
    file_path = Path(selected_session["path"])
    
    if feedback.confirm(f"Load session '{selected_session['name']}'? This will replace your current session."):
        success = session.resume(file_path, feedback)
        if success:
            feedback.info("Session loaded successfully. Returning to main menu.")
            # Return to main menu after loading
            return "MAIN"
    
    return "CONTINUE"


def _list_sessions(ctx: Context, feedback) -> str:
    """List all saved sessions."""
    sessions = session.list_saved_sessions()
    
    if not sessions:
        feedback.info("No saved sessions found")
        return "CONTINUE"
    
    console = Console()
    table = Table(title="Saved Sessions")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="yellow")
    table.add_column("States", style="green")
    table.add_column("Created", style="blue")
    
    for sess in sessions:
        # Format the created date
        created = sess["created"]
        if "T" in created:
            created = created.split("T")[0]  # Just show the date part
        
        table.add_row(
            sess["name"],
            sess["description"][:40] + "..." if len(sess["description"]) > 40 else sess["description"],
            str(sess["state_count"]),
            created
        )
    
    console.print(table)
    feedback.pause_for_user()
    
    return "CONTINUE"


def _cleanup_sessions(ctx: Context, feedback) -> str:
    """Clean up old sessions."""
    sessions = session.list_saved_sessions()
    
    if len(sessions) <= 5:
        feedback.info("No cleanup needed. You have 5 or fewer sessions.")
        return "CONTINUE"
    
    max_sessions_str = ctx.selector.ask("How many sessions to keep? (default: 10)")
    try:
        max_sessions = int(max_sessions_str) if max_sessions_str else 10
    except ValueError:
        feedback.error("Invalid number entered")
        return "CONTINUE"
    
    if feedback.confirm(f"Delete sessions older than the {max_sessions} most recent?"):
        deleted_count = session.cleanup_old_sessions(max_sessions)
        feedback.success(f"Deleted {deleted_count} old sessions")
    
    return "CONTINUE"


def _create_backup(ctx: Context, feedback) -> str:
    """Create a manual backup."""
    backup_name = ctx.selector.ask("Enter backup name (optional):")
    
    success = session.create_manual_backup(backup_name or "")
    if success:
        feedback.success("Manual backup created successfully")
    
    return "CONTINUE"


def _session_settings(ctx: Context, feedback) -> str:
    """Configure session settings."""
    current_auto_save = session._auto_save_enabled
    
    choices = [
        f"Auto-Save: {'Enabled' if current_auto_save else 'Disabled'}",
        "Clear Auto-Save File",
        "Clear Crash Backup",
        "Back"
    ]
    
    choice = ctx.selector.choose(
        "Session Settings:",
        choices=choices
    )
    
    if choice and choice.startswith("Auto-Save"):
        new_setting = not current_auto_save
        session.enable_auto_save(new_setting)
        feedback.success(f"Auto-save {'enabled' if new_setting else 'disabled'}")
    
    elif choice == "Clear Auto-Save File":
        if feedback.confirm("Clear the auto-save file?"):
            session._session_manager.clear_auto_save()
            feedback.success("Auto-save file cleared")
    
    elif choice == "Clear Crash Backup":
        if feedback.confirm("Clear the crash backup file?"):
            session._session_manager.clear_crash_backup()
            feedback.success("Crash backup cleared")
    
    return "CONTINUE"
