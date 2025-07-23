"""
Watch History Management Menu for the interactive CLI.
Provides comprehensive watch history viewing, editing, and management capabilities.
"""

import logging
from pathlib import Path
from typing import Callable, Dict, List

from rich.console import Console
from rich.table import Table
from rich.text import Text

from ....core.constants import APP_DATA_DIR
from ...utils.feedback import create_feedback_manager
from ...utils.watch_history_manager import WatchHistoryManager
from ...utils.watch_history_types import WatchHistoryEntry
from ..session import Context, session
from ..state import InternalDirective, State

logger = logging.getLogger(__name__)

MenuAction = Callable[[], str]


@session.menu
def watch_history(ctx: Context, state: State) -> State | InternalDirective:
    """
    Watch history management menu for viewing and managing local watch history.
    """
    icons = ctx.config.general.icons
    feedback = create_feedback_manager(icons)
    console = Console()
    console.clear()

    # Initialize watch history manager
    history_manager = WatchHistoryManager()

    # Show watch history stats
    _display_history_stats(console, history_manager, icons)

    options: Dict[str, MenuAction] = {
        f"{'📺 ' if icons else ''}Currently Watching": lambda: _view_watching(
            ctx, history_manager, feedback
        ),
        f"{'✅ ' if icons else ''}Completed Anime": lambda: _view_completed(
            ctx, history_manager, feedback
        ),
        f"{'🕒 ' if icons else ''}Recently Watched": lambda: _view_recent(
            ctx, history_manager, feedback
        ),
        f"{'📋 ' if icons else ''}View All History": lambda: _view_all_history(
            ctx, history_manager, feedback
        ),
        f"{'🔍 ' if icons else ''}Search History": lambda: _search_history(
            ctx, history_manager, feedback
        ),
        f"{'✏️ ' if icons else ''}Edit Entry": lambda: _edit_entry(
            ctx, history_manager, feedback
        ),
        f"{'🗑️ ' if icons else ''}Remove Entry": lambda: _remove_entry(
            ctx, history_manager, feedback
        ),
        f"{'📊 ' if icons else ''}View Statistics": lambda: _view_stats(
            ctx, history_manager, feedback
        ),
        f"{'💾 ' if icons else ''}Export History": lambda: _export_history(
            ctx, history_manager, feedback
        ),
        f"{'📥 ' if icons else ''}Import History": lambda: _import_history(
            ctx, history_manager, feedback
        ),
        f"{'🧹 ' if icons else ''}Clear All History": lambda: _clear_history(
            ctx, history_manager, feedback
        ),
        f"{'🔙 ' if icons else ''}Back to Main Menu": lambda: "BACK",
    }

    choice_str = ctx.selector.choose(
        prompt="Select Watch History Action",
        choices=list(options.keys()),
        header="Watch History Management",
    )

    if not choice_str:
        return InternalDirective.BACK

    result = options[choice_str]()

    if result == "BACK":
        return InternalDirective.BACK
    else:
        return InternalDirective.CONTINUE


def _display_history_stats(
    console: Console, history_manager: WatchHistoryManager, icons: bool
):
    """Display current watch history statistics."""
    stats = history_manager.get_stats()

    # Create a stats table
    table = Table(title=f"{'📊 ' if icons else ''}Watch History Overview")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green")

    table.add_row("Total Anime", str(stats["total_entries"]))
    table.add_row("Currently Watching", str(stats["watching"]))
    table.add_row("Completed", str(stats["completed"]))
    table.add_row("Dropped", str(stats["dropped"]))
    table.add_row("Paused", str(stats["paused"]))
    table.add_row("Total Episodes", str(stats["total_episodes_watched"]))
    table.add_row("Last Updated", stats["last_updated"])

    console.print(table)
    console.print()


def _view_watching(ctx: Context, history_manager: WatchHistoryManager, feedback) -> str:
    """View currently watching anime."""
    entries = history_manager.get_watching_entries()

    if not entries:
        feedback.info("No anime currently being watched")
        return "CONTINUE"

    return _display_entries_list(ctx, entries, "Currently Watching", feedback)


def _view_completed(
    ctx: Context, history_manager: WatchHistoryManager, feedback
) -> str:
    """View completed anime."""
    entries = history_manager.get_completed_entries()

    if not entries:
        feedback.info("No completed anime found")
        return "CONTINUE"

    return _display_entries_list(ctx, entries, "Completed Anime", feedback)


def _view_recent(ctx: Context, history_manager: WatchHistoryManager, feedback) -> str:
    """View recently watched anime."""
    entries = history_manager.get_recently_watched(20)

    if not entries:
        feedback.info("No recent watch history found")
        return "CONTINUE"

    return _display_entries_list(ctx, entries, "Recently Watched", feedback)


def _view_all_history(
    ctx: Context, history_manager: WatchHistoryManager, feedback
) -> str:
    """View all watch history entries."""
    entries = history_manager.get_all_entries()

    if not entries:
        feedback.info("No watch history found")
        return "CONTINUE"

    # Sort by last watched date
    entries.sort(key=lambda x: x.last_watched, reverse=True)

    return _display_entries_list(ctx, entries, "All Watch History", feedback)


def _search_history(
    ctx: Context, history_manager: WatchHistoryManager, feedback
) -> str:
    """Search watch history by title."""
    query = ctx.selector.ask("Enter search query:")

    if not query:
        return "CONTINUE"

    entries = history_manager.search_entries(query)

    if not entries:
        feedback.info(f"No anime found matching '{query}'")
        return "CONTINUE"

    return _display_entries_list(
        ctx, entries, f"Search Results for '{query}'", feedback
    )


def _display_entries_list(
    ctx: Context, entries: List[WatchHistoryEntry], title: str, feedback
) -> str:
    """Display a list of watch history entries and allow selection."""
    console = Console()
    console.clear()

    # Create table for entries
    table = Table(title=title)
    table.add_column("Status", style="yellow", width=6)
    table.add_column("Title", style="cyan")
    table.add_column("Progress", style="green", width=12)
    table.add_column("Last Watched", style="blue", width=12)

    choices = []
    entry_map = {}

    for i, entry in enumerate(entries):
        # Format last watched date
        last_watched = entry.last_watched.strftime("%Y-%m-%d")

        # Add to table
        table.add_row(
            entry.get_status_emoji(),
            entry.get_display_title(),
            entry.get_progress_display(),
            last_watched,
        )

        # Create choice for selector
        choice_text = f"{entry.get_status_emoji()} {entry.get_display_title()} - {entry.get_progress_display()}"
        choices.append(choice_text)
        entry_map[choice_text] = entry

    console.print(table)
    console.print()

    if not choices:
        feedback.info("No entries to display")
        feedback.pause_for_user()
        return "CONTINUE"

    choices.append("Back")

    choice = ctx.selector.choose("Select an anime for details:", choices=choices)

    if not choice or choice == "Back":
        return "CONTINUE"

    selected_entry = entry_map[choice]
    return _show_entry_details(ctx, selected_entry, feedback)


def _show_entry_details(ctx: Context, entry: WatchHistoryEntry, feedback) -> str:
    """Show detailed information about a watch history entry."""
    console = Console()
    console.clear()

    # Display detailed entry information
    console.print(f"[bold cyan]{entry.get_display_title()}[/bold cyan]")
    console.print(f"Status: {entry.get_status_emoji()} {entry.status.title()}")
    console.print(f"Progress: {entry.get_progress_display()}")
    console.print(f"Times Watched: {entry.times_watched}")
    console.print(f"First Watched: {entry.first_watched.strftime('%Y-%m-%d %H:%M')}")
    console.print(f"Last Watched: {entry.last_watched.strftime('%Y-%m-%d %H:%M')}")

    if entry.notes:
        console.print(f"Notes: {entry.notes}")

    # Show media details if available
    media = entry.media_item
    if media.description:
        console.print(
            f"\nDescription: {media.description[:200]}{'...' if len(media.description) > 200 else ''}"
        )

    if media.genres:
        console.print(f"Genres: {', '.join(media.genres)}")

    if media.average_score:
        console.print(f"Score: {media.average_score}/100")

    console.print()

    # Action options
    actions = [
        "Mark Episode as Watched",
        "Change Status",
        "Edit Notes",
        "Remove from History",
        "Back to List",
    ]

    choice = ctx.selector.choose("Select action:", choices=actions)

    if choice == "Mark Episode as Watched":
        return _mark_episode_watched(ctx, entry, feedback)
    elif choice == "Change Status":
        return _change_entry_status(ctx, entry, feedback)
    elif choice == "Edit Notes":
        return _edit_entry_notes(ctx, entry, feedback)
    elif choice == "Remove from History":
        return _confirm_remove_entry(ctx, entry, feedback)
    else:
        return "CONTINUE"


def _mark_episode_watched(ctx: Context, entry: WatchHistoryEntry, feedback) -> str:
    """Mark a specific episode as watched."""
    current_episode = entry.last_watched_episode
    max_episodes = entry.media_item.episodes or 999

    episode_str = ctx.selector.ask(
        f"Enter episode number (current: {current_episode}, max: {max_episodes}):"
    )

    try:
        episode = int(episode_str)
        if episode < 1 or (max_episodes and episode > max_episodes):
            feedback.error(
                f"Invalid episode number. Must be between 1 and {max_episodes}"
            )
            return "CONTINUE"

        history_manager = WatchHistoryManager()
        success = history_manager.mark_episode_watched(entry.media_item.id, episode)

        if success:
            feedback.success(f"Marked episode {episode} as watched")
        else:
            feedback.error("Failed to update watch progress")

    except ValueError:
        feedback.error("Invalid episode number entered")

    return "CONTINUE"


def _change_entry_status(ctx: Context, entry: WatchHistoryEntry, feedback) -> str:
    """Change the status of a watch history entry."""
    statuses = ["watching", "completed", "paused", "dropped", "planning"]
    current_status = entry.status

    choices = [
        f"{status.title()} {'(current)' if status == current_status else ''}"
        for status in statuses
    ]
    choices.append("Cancel")

    choice = ctx.selector.choose(
        f"Select new status (current: {current_status}):", choices=choices
    )

    if not choice or choice == "Cancel":
        return "CONTINUE"

    new_status = choice.split()[0].lower()

    history_manager = WatchHistoryManager()
    success = history_manager.change_status(entry.media_item.id, new_status)

    if success:
        feedback.success(f"Changed status to {new_status}")
    else:
        feedback.error("Failed to update status")

    return "CONTINUE"


def _edit_entry_notes(ctx: Context, entry: WatchHistoryEntry, feedback) -> str:
    """Edit notes for a watch history entry."""
    current_notes = entry.notes or ""

    new_notes = ctx.selector.ask(f"Enter notes (current: '{current_notes}'):")

    if new_notes is None:  # User cancelled
        return "CONTINUE"

    history_manager = WatchHistoryManager()
    success = history_manager.update_notes(entry.media_item.id, new_notes)

    if success:
        feedback.success("Notes updated successfully")
    else:
        feedback.error("Failed to update notes")

    return "CONTINUE"


def _confirm_remove_entry(ctx: Context, entry: WatchHistoryEntry, feedback) -> str:
    """Confirm and remove a watch history entry."""
    if feedback.confirm(f"Remove '{entry.get_display_title()}' from watch history?"):
        history_manager = WatchHistoryManager()
        success = history_manager.remove_entry(entry.media_item.id)

        if success:
            feedback.success("Entry removed from watch history")
        else:
            feedback.error("Failed to remove entry")

    return "CONTINUE"


def _edit_entry(ctx: Context, history_manager: WatchHistoryManager, feedback) -> str:
    """Edit a watch history entry (select first)."""
    entries = history_manager.get_all_entries()

    if not entries:
        feedback.info("No watch history entries to edit")
        return "CONTINUE"

    # Sort by title for easier selection
    entries.sort(key=lambda x: x.get_display_title())

    choices = [
        f"{entry.get_display_title()} - {entry.get_progress_display()}"
        for entry in entries
    ]
    choices.append("Cancel")

    choice = ctx.selector.choose("Select anime to edit:", choices=choices)

    if not choice or choice == "Cancel":
        return "CONTINUE"

    # Find the selected entry
    choice_title = choice.split(" - ")[0]
    selected_entry = next(
        (entry for entry in entries if entry.get_display_title() == choice_title), None
    )

    if selected_entry:
        return _show_entry_details(ctx, selected_entry, feedback)

    return "CONTINUE"


def _remove_entry(ctx: Context, history_manager: WatchHistoryManager, feedback) -> str:
    """Remove a watch history entry (select first)."""
    entries = history_manager.get_all_entries()

    if not entries:
        feedback.info("No watch history entries to remove")
        return "CONTINUE"

    # Sort by title for easier selection
    entries.sort(key=lambda x: x.get_display_title())

    choices = [
        f"{entry.get_display_title()} - {entry.get_progress_display()}"
        for entry in entries
    ]
    choices.append("Cancel")

    choice = ctx.selector.choose("Select anime to remove:", choices=choices)

    if not choice or choice == "Cancel":
        return "CONTINUE"

    # Find the selected entry
    choice_title = choice.split(" - ")[0]
    selected_entry = next(
        (entry for entry in entries if entry.get_display_title() == choice_title), None
    )

    if selected_entry:
        return _confirm_remove_entry(ctx, selected_entry, feedback)

    return "CONTINUE"


def _view_stats(ctx: Context, history_manager: WatchHistoryManager, feedback) -> str:
    """View detailed watch history statistics."""
    console = Console()
    console.clear()

    stats = history_manager.get_stats()

    # Create detailed stats table
    table = Table(title="Detailed Watch History Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Anime Entries", str(stats["total_entries"]))
    table.add_row("Currently Watching", str(stats["watching"]))
    table.add_row("Completed", str(stats["completed"]))
    table.add_row("Dropped", str(stats["dropped"]))
    table.add_row("Paused", str(stats["paused"]))
    table.add_row("Total Episodes Watched", str(stats["total_episodes_watched"]))
    table.add_row("Last Updated", stats["last_updated"])

    # Calculate additional stats
    if stats["total_entries"] > 0:
        completion_rate = (stats["completed"] / stats["total_entries"]) * 100
        table.add_row("Completion Rate", f"{completion_rate:.1f}%")

        avg_episodes = stats["total_episodes_watched"] / stats["total_entries"]
        table.add_row("Avg Episodes per Anime", f"{avg_episodes:.1f}")

    console.print(table)
    feedback.pause_for_user()

    return "CONTINUE"


def _export_history(
    ctx: Context, history_manager: WatchHistoryManager, feedback
) -> str:
    """Export watch history to a file."""
    export_name = ctx.selector.ask("Enter export filename (without extension):")

    if not export_name:
        return "CONTINUE"

    export_path = APP_DATA_DIR / f"{export_name}.json"

    if export_path.exists():
        if not feedback.confirm(
            f"File '{export_name}.json' already exists. Overwrite?"
        ):
            return "CONTINUE"

    success = history_manager.export_history(export_path)

    if success:
        feedback.success(f"Watch history exported to {export_path}")
    else:
        feedback.error("Failed to export watch history")

    return "CONTINUE"


def _import_history(
    ctx: Context, history_manager: WatchHistoryManager, feedback
) -> str:
    """Import watch history from a file."""
    import_name = ctx.selector.ask("Enter import filename (without extension):")

    if not import_name:
        return "CONTINUE"

    import_path = APP_DATA_DIR / f"{import_name}.json"

    if not import_path.exists():
        feedback.error(f"File '{import_name}.json' not found in {APP_DATA_DIR}")
        return "CONTINUE"

    merge = feedback.confirm(
        "Merge with existing history? (No = Replace existing history)"
    )

    success = history_manager.import_history(import_path, merge=merge)

    if success:
        action = "merged with" if merge else "replaced"
        feedback.success(f"Watch history imported and {action} existing data")
    else:
        feedback.error("Failed to import watch history")

    return "CONTINUE"


def _clear_history(ctx: Context, history_manager: WatchHistoryManager, feedback) -> str:
    """Clear all watch history with confirmation."""
    if not feedback.confirm(
        "Are you sure you want to clear ALL watch history? This cannot be undone."
    ):
        return "CONTINUE"

    if not feedback.confirm("Final confirmation: Clear all watch history?"):
        return "CONTINUE"

    # Create backup before clearing
    backup_success = history_manager.backup_history()
    if backup_success:
        feedback.info("Backup created before clearing")

    success = history_manager.clear_history()

    if success:
        feedback.success("All watch history cleared")
    else:
        feedback.error("Failed to clear watch history")

    return "CONTINUE"
