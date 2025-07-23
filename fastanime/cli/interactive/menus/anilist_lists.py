"""
AniList Watch List Operations Menu
Implements Step 8: Remote Watch List Operations

Provides comprehensive AniList list management including:
- Viewing user lists (Watching, Completed, Planning, etc.)
- Interactive list selection and navigation
- Adding/removing anime from lists
- List statistics and overview
"""

import logging
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ....libs.api.params import UpdateListEntryParams, UserListParams
from ....libs.api.types import MediaItem, MediaSearchResult, UserListItem
from ...utils.feedback import create_feedback_manager, execute_with_feedback
from ..session import Context, session
from ..state import ControlFlow, MediaApiState, State

logger = logging.getLogger(__name__)


@session.menu
def anilist_lists(ctx: Context, state: State) -> State | ControlFlow:
    """
    Main AniList lists management menu.
    Shows all user lists with statistics and navigation options.
    """
    icons = ctx.config.general.icons
    feedback = create_feedback_manager(icons)
    console = Console()
    console.clear()

    # Check authentication
    if not ctx.media_api.user_profile:
        feedback.error(
            "Authentication Required",
            "You must be logged in to access your AniList lists. Please authenticate first.",
        )
        feedback.pause_for_user("Press Enter to continue")
        return State(menu_name="AUTH")

    # Display user profile and lists overview
    _display_lists_overview(console, ctx, icons)

    # Menu options
    options = [
        f"{'📺 ' if icons else ''}Currently Watching",
        f"{'📋 ' if icons else ''}Planning to Watch",
        f"{'✅ ' if icons else ''}Completed",
        f"{'⏸️ ' if icons else ''}Paused",
        f"{'🚮 ' if icons else ''}Dropped",
        f"{'🔁 ' if icons else ''}Rewatching",
        f"{'📊 ' if icons else ''}View All Lists Statistics",
        f"{'🔍 ' if icons else ''}Search Across All Lists",
        f"{'➕ ' if icons else ''}Add Anime to List",
        f"{'↩️ ' if icons else ''}Back to Main Menu",
    ]

    choice = ctx.selector.choose(
        prompt="Select List Action",
        choices=options,
        header=f"AniList Lists - {ctx.media_api.user_profile.name}",
    )

    if not choice:
        return ControlFlow.BACK

    # Handle menu choices
    if "Currently Watching" in choice:
        return _navigate_to_list(ctx, "CURRENT")
    elif "Planning to Watch" in choice:
        return _navigate_to_list(ctx, "PLANNING")
    elif "Completed" in choice:
        return _navigate_to_list(ctx, "COMPLETED")
    elif "Paused" in choice:
        return _navigate_to_list(ctx, "PAUSED")
    elif "Dropped" in choice:
        return _navigate_to_list(ctx, "DROPPED")
    elif "Rewatching" in choice:
        return _navigate_to_list(ctx, "REPEATING")
    elif "View All Lists Statistics" in choice:
        return _show_all_lists_stats(ctx, feedback, icons)
    elif "Search Across All Lists" in choice:
        return _search_all_lists(ctx, feedback, icons)
    elif "Add Anime to List" in choice:
        return _add_anime_to_list(ctx, feedback, icons)
    else:  # Back to Main Menu
        return ControlFlow.BACK


@session.menu
def anilist_list_view(ctx: Context, state: State) -> State | ControlFlow:
    """
    View and manage a specific AniList list (e.g., Watching, Completed).
    """
    icons = ctx.config.general.icons
    feedback = create_feedback_manager(icons)
    console = Console()
    console.clear()

    # Get list status from state data
    list_status = state.data.get("list_status") if state.data else "CURRENT"
    page = state.data.get("page", 1) if state.data else 1

    # Fetch list data
    def fetch_list():
        return ctx.media_api.search_media_list(
            UserListParams(status=list_status, page=page, per_page=20)
        )

    success, result = execute_with_feedback(
        fetch_list,
        feedback,
        f"fetch {_status_to_display_name(list_status)} list",
        loading_msg=f"Loading {_status_to_display_name(list_status)} list...",
        success_msg=f"Loaded {_status_to_display_name(list_status)} list",
        error_msg=f"Failed to load {_status_to_display_name(list_status)} list",
    )

    if not success or not result:
        feedback.pause_for_user("Press Enter to continue")
        return ControlFlow.BACK

    # Display list contents
    _display_list_contents(console, result, list_status, page, icons)

    # Menu options
    options = [
        f"{'👁️ ' if icons else ''}View/Edit Anime Details",
        f"{'🔄 ' if icons else ''}Refresh List",
        f"{'➕ ' if icons else ''}Add New Anime",
        f"{'🗑️ ' if icons else ''}Remove from List",
    ]

    # Add pagination options
    if result.page_info.has_next_page:
        options.append(f"{'➡️ ' if icons else ''}Next Page")
    if page > 1:
        options.append(f"{'⬅️ ' if icons else ''}Previous Page")

    options.extend(
        [
            f"{'📊 ' if icons else ''}List Statistics",
            f"{'↩️ ' if icons else ''}Back to Lists Menu",
        ]
    )

    choice = ctx.selector.choose(
        prompt="Select Action",
        choices=options,
        header=f"{_status_to_display_name(list_status)} - Page {page}",
    )

    if not choice:
        return ControlFlow.BACK

    # Handle menu choices
    if "View/Edit Anime Details" in choice:
        return _select_anime_for_details(ctx, result, list_status, page)
    elif "Refresh List" in choice:
        return ControlFlow.CONTINUE
    elif "Add New Anime" in choice:
        return _add_anime_to_specific_list(ctx, list_status, feedback, icons)
    elif "Remove from List" in choice:
        return _remove_anime_from_list(ctx, result, list_status, page, feedback, icons)
    elif "Next Page" in choice:
        return State(
            menu_name="ANILIST_LIST_VIEW",
            data={"list_status": list_status, "page": page + 1},
        )
    elif "Previous Page" in choice:
        return State(
            menu_name="ANILIST_LIST_VIEW",
            data={"list_status": list_status, "page": page - 1},
        )
    elif "List Statistics" in choice:
        return _show_list_statistics(ctx, list_status, feedback, icons)
    else:  # Back to Lists Menu
        return State(menu_name="ANILIST_LISTS")


@session.menu
def anilist_anime_details(ctx: Context, state: State) -> State | ControlFlow:
    """
    View and edit details for a specific anime in a user's list.
    """
    icons = ctx.config.general.icons
    feedback = create_feedback_manager(icons)
    console = Console()
    console.clear()

    # Get anime and list info from state
    if not state.data:
        return ControlFlow.BACK

    anime = state.data.get("anime")
    list_status = state.data.get("list_status")
    return_page = state.data.get("return_page", 1)
    from_media_actions = state.data.get("from_media_actions", False)

    if not anime:
        return ControlFlow.BACK

    # Display anime details
    _display_anime_list_details(console, anime, icons)

    # Menu options
    options = [
        f"{'✏️ ' if icons else ''}Edit Progress",
        f"{'⭐ ' if icons else ''}Edit Rating",
        f"{'📝 ' if icons else ''}Edit Status",
        f"{'🎬 ' if icons else ''}Watch/Stream",
        f"{'🗑️ ' if icons else ''}Remove from List",
        f"{'↩️ ' if icons else ''}Back to List",
    ]

    choice = ctx.selector.choose(
        prompt="Select Action",
        choices=options,
        header=f"{anime.title.english or anime.title.romaji}",
    )

    if not choice:
        # Return to appropriate menu based on how we got here
        if from_media_actions:
            return ControlFlow.BACK
        elif list_status:
            return State(
                menu_name="ANILIST_LIST_VIEW",
                data={"list_status": list_status, "page": return_page},
            )
        else:
            return State(menu_name="ANILIST_LISTS")

    # Handle menu choices
    if "Edit Progress" in choice:
        return _edit_anime_progress(
            ctx, anime, list_status, return_page, feedback, from_media_actions
        )
    elif "Edit Rating" in choice:
        return _edit_anime_rating(
            ctx, anime, list_status, return_page, feedback, from_media_actions
        )
    elif "Edit Status" in choice:
        return _edit_anime_status(
            ctx, anime, list_status, return_page, feedback, from_media_actions
        )
    elif "Watch/Stream" in choice:
        return _stream_anime(ctx, anime)
    elif "Remove from List" in choice:
        return _confirm_remove_anime(
            ctx, anime, list_status, return_page, feedback, icons, from_media_actions
        )
    else:  # Back to List/Media Actions
        # Return to appropriate menu based on how we got here
        if from_media_actions:
            return ControlFlow.BACK
        elif list_status:
            return State(
                menu_name="ANILIST_LIST_VIEW",
                data={"list_status": list_status, "page": return_page},
            )
        else:
            return State(menu_name="ANILIST_LISTS")


def _display_lists_overview(console: Console, ctx: Context, icons: bool):
    """Display overview of all user lists with counts."""
    user = ctx.media_api.user_profile

    # Create overview panel
    overview_text = f"[bold cyan]{user.name}[/bold cyan]'s AniList Management\n"
    overview_text += f"User ID: {user.id}\n\n"
    overview_text += "Manage your anime lists, track progress, and sync with AniList"

    panel = Panel(
        overview_text,
        title=f"{'📚 ' if icons else ''}AniList Lists Overview",
        border_style="cyan",
    )
    console.print(panel)
    console.print()


def _display_list_contents(
    console: Console,
    result: MediaSearchResult,
    list_status: str,
    page: int,
    icons: bool,
):
    """Display the contents of a specific list in a table."""
    if not result.media:
        console.print(
            f"[yellow]No anime found in {_status_to_display_name(list_status)} list[/yellow]"
        )
        return

    table = Table(title=f"{_status_to_display_name(list_status)} - Page {page}")
    table.add_column("Title", style="cyan", no_wrap=False, width=40)
    table.add_column("Episodes", justify="center", width=10)
    table.add_column("Progress", justify="center", width=10)
    table.add_column("Score", justify="center", width=8)
    table.add_column("Status", justify="center", width=12)

    for i, anime in enumerate(result.media, 1):
        title = anime.title.english or anime.title.romaji or "Unknown Title"
        episodes = str(anime.episodes or "?")

        # Get list entry details if available
        progress = "?"
        score = "?"
        status = _status_to_display_name(list_status)

        # Note: In a real implementation, you'd get these from the MediaList entry
        # For now, we'll show placeholders
        if hasattr(anime, "media_list_entry") and anime.media_list_entry:
            progress = str(anime.media_list_entry.progress or 0)
            score = str(anime.media_list_entry.score or "-")

        table.add_row(f"{i}. {title}", episodes, progress, score, status)

    console.print(table)
    console.print(
        f"\nShowing {len(result.media)} anime from {_status_to_display_name(list_status)} list"
    )

    # Show pagination info
    if result.page_info.has_next_page:
        console.print(f"[dim]More results available on next page[/dim]")


def _display_anime_list_details(console: Console, anime: MediaItem, icons: bool):
    """Display detailed information about an anime in the user's list."""
    title = anime.title.english or anime.title.romaji or "Unknown Title"

    details_text = f"[bold]{title}[/bold]\n\n"
    details_text += f"Episodes: {anime.episodes or 'Unknown'}\n"
    details_text += f"Status: {anime.status or 'Unknown'}\n"
    details_text += (
        f"Genres: {', '.join(anime.genres) if anime.genres else 'Unknown'}\n"
    )

    if anime.description:
        # Truncate description for display
        desc = (
            anime.description[:300] + "..."
            if len(anime.description) > 300
            else anime.description
        )
        details_text += f"\nDescription:\n{desc}"

    # Add list-specific information if available
    if hasattr(anime, "media_list_entry") and anime.media_list_entry:
        entry = anime.media_list_entry
        details_text += f"\n\n[bold cyan]Your List Info:[/bold cyan]\n"
        details_text += f"Progress: {entry.progress or 0} episodes\n"
        details_text += f"Score: {entry.score or 'Not rated'}\n"
        details_text += f"Status: {_status_to_display_name(entry.status) if hasattr(entry, 'status') else 'Unknown'}\n"

    panel = Panel(
        details_text,
        title=f"{'📺 ' if icons else ''}Anime Details",
        border_style="blue",
    )
    console.print(panel)


def _navigate_to_list(ctx: Context, list_status: UserListItem) -> State:
    """Navigate to a specific list view."""
    return State(
        menu_name="ANILIST_LIST_VIEW", data={"list_status": list_status, "page": 1}
    )


def _select_anime_for_details(
    ctx: Context, result: MediaSearchResult, list_status: str, page: int
) -> State | ControlFlow:
    """Let user select an anime from the list to view/edit details."""
    if not result.media:
        return ControlFlow.CONTINUE

    # Create choices from anime list
    choices = []
    for i, anime in enumerate(result.media, 1):
        title = anime.title.english or anime.title.romaji or "Unknown Title"
        choices.append(f"{i}. {title}")

    choice = ctx.selector.choose(
        prompt="Select anime to view/edit",
        choices=choices,
        header="Select Anime",
    )

    if not choice:
        return ControlFlow.CONTINUE

    # Extract index and get selected anime
    try:
        index = int(choice.split(".")[0]) - 1
        selected_anime = result.media[index]

        return State(
            menu_name="ANILIST_ANIME_DETAILS",
            data={
                "anime": selected_anime,
                "list_status": list_status,
                "return_page": page,
            },
        )
    except (ValueError, IndexError):
        return ControlFlow.CONTINUE


def _edit_anime_progress(
    ctx: Context,
    anime: MediaItem,
    list_status: str,
    return_page: int,
    feedback,
    from_media_actions: bool = False,
) -> State | ControlFlow:
    """Edit the progress (episodes watched) for an anime."""
    current_progress = 0
    if hasattr(anime, "media_list_entry") and anime.media_list_entry:
        current_progress = anime.media_list_entry.progress or 0

    max_episodes = anime.episodes or 999

    try:
        new_progress = click.prompt(
            f"Enter new progress (0-{max_episodes}, current: {current_progress})",
            type=int,
            default=current_progress,
        )

        if new_progress < 0 or new_progress > max_episodes:
            feedback.error(
                "Invalid progress", f"Progress must be between 0 and {max_episodes}"
            )
            feedback.pause_for_user("Press Enter to continue")
            return ControlFlow.CONTINUE

        # Update via API
        def update_progress():
            return ctx.media_api.update_list_entry(
                UpdateListEntryParams(media_id=anime.id, progress=new_progress)
            )

        success, _ = execute_with_feedback(
            update_progress,
            feedback,
            "update progress",
            loading_msg="Updating progress...",
            success_msg=f"Progress updated to {new_progress} episodes",
            error_msg="Failed to update progress",
        )

        if success:
            feedback.pause_for_user("Press Enter to continue")

    except click.Abort:
        pass

    # Return to appropriate menu based on how we got here
    if from_media_actions:
        return ControlFlow.BACK
    elif list_status:
        return State(
            menu_name="ANILIST_LIST_VIEW",
            data={"list_status": list_status, "page": return_page},
        )
    else:
        return State(menu_name="ANILIST_LISTS")


def _edit_anime_rating(
    ctx: Context,
    anime: MediaItem,
    list_status: str,
    return_page: int,
    feedback,
    from_media_actions: bool = False,
) -> State | ControlFlow:
    """Edit the rating/score for an anime."""
    current_score = 0.0
    if hasattr(anime, "media_list_entry") and anime.media_list_entry:
        current_score = anime.media_list_entry.score or 0.0

    try:
        new_score = click.prompt(
            f"Enter new rating (0.0-10.0, current: {current_score})",
            type=float,
            default=current_score,
        )

        if new_score < 0.0 or new_score > 10.0:
            feedback.error("Invalid rating", "Rating must be between 0.0 and 10.0")
            feedback.pause_for_user("Press Enter to continue")
            return ControlFlow.CONTINUE

        # Update via API
        def update_score():
            return ctx.media_api.update_list_entry(
                UpdateListEntryParams(media_id=anime.id, score=new_score)
            )

        success, _ = execute_with_feedback(
            update_score,
            feedback,
            "update rating",
            loading_msg="Updating rating...",
            success_msg=f"Rating updated to {new_score}/10",
            error_msg="Failed to update rating",
        )

        if success:
            feedback.pause_for_user("Press Enter to continue")

    except click.Abort:
        pass

    # Return to appropriate menu based on how we got here
    if from_media_actions:
        return ControlFlow.BACK
    elif list_status:
        return State(
            menu_name="ANILIST_LIST_VIEW",
            data={"list_status": list_status, "page": return_page},
        )
    else:
        return State(menu_name="ANILIST_LISTS")


def _edit_anime_status(
    ctx: Context,
    anime: MediaItem,
    list_status: str,
    return_page: int,
    feedback,
    from_media_actions: bool = False,
) -> State | ControlFlow:
    """Edit the list status for an anime."""
    status_options = [
        "CURRENT (Currently Watching)",
        "PLANNING (Plan to Watch)",
        "COMPLETED (Completed)",
        "PAUSED (Paused)",
        "DROPPED (Dropped)",
        "REPEATING (Rewatching)",
    ]

    choice = ctx.selector.choose(
        prompt="Select new status",
        choices=status_options,
        header="Change List Status",
    )

    if not choice:
        return ControlFlow.CONTINUE

    new_status = choice.split(" ")[0]

    # Update via API
    def update_status():
        return ctx.media_api.update_list_entry(
            UpdateListEntryParams(media_id=anime.id, status=new_status)
        )

    success, _ = execute_with_feedback(
        update_status,
        feedback,
        "update status",
        loading_msg="Updating status...",
        success_msg=f"Status updated to {_status_to_display_name(new_status)}",
        error_msg="Failed to update status",
    )

    if success:
        feedback.pause_for_user("Press Enter to continue")

        # If status changed, return to main lists menu since the anime
        # is no longer in the current list
        if new_status != list_status:
            if from_media_actions:
                return ControlFlow.BACK
            else:
                return State(menu_name="ANILIST_LISTS")

    # Return to appropriate menu based on how we got here
    if from_media_actions:
        return ControlFlow.BACK
    elif list_status:
        return State(
            menu_name="ANILIST_LIST_VIEW",
            data={"list_status": list_status, "page": return_page},
        )
    else:
        return State(menu_name="ANILIST_LISTS")


def _confirm_remove_anime(
    ctx: Context,
    anime: MediaItem,
    list_status: str,
    return_page: int,
    feedback,
    icons: bool,
    from_media_actions: bool = False,
) -> State | ControlFlow:
    """Confirm and remove an anime from the user's list."""
    title = anime.title.english or anime.title.romaji or "Unknown Title"

    if not feedback.confirm(
        f"Remove '{title}' from your {_status_to_display_name(list_status)} list?",
        default=False,
    ):
        return ControlFlow.CONTINUE

    # Remove via API
    def remove_anime():
        return ctx.media_api.delete_list_entry(anime.id)

    success, _ = execute_with_feedback(
        remove_anime,
        feedback,
        "remove anime",
        loading_msg="Removing anime from list...",
        success_msg=f"'{title}' removed from list",
        error_msg="Failed to remove anime from list",
    )

    if success:
        feedback.pause_for_user("Press Enter to continue")

    # Return to appropriate menu based on how we got here
    if from_media_actions:
        return ControlFlow.BACK
    elif list_status:
        return State(
            menu_name="ANILIST_LIST_VIEW",
            data={"list_status": list_status, "page": return_page},
        )
    else:
        return State(menu_name="ANILIST_LISTS")


def _stream_anime(ctx: Context, anime: MediaItem) -> State:
    """Navigate to streaming interface for the selected anime."""
    return State(
        menu_name="RESULTS",
        data=MediaApiState(
            results=[anime],  # Pass as single-item list
            query=anime.title.english or anime.title.romaji or "Unknown",
            page=1,
            api_params=None,
            user_list_params=None,
        ),
    )


def _show_all_lists_stats(ctx: Context, feedback, icons: bool) -> State | ControlFlow:
    """Show comprehensive statistics across all user lists."""
    console = Console()
    console.clear()

    # This would require fetching data from all lists
    # For now, show a placeholder implementation
    stats_text = "[bold cyan]📊 Your AniList Statistics[/bold cyan]\n\n"
    stats_text += "[dim]Loading comprehensive list statistics...[/dim]\n"
    stats_text += "[dim]This feature requires fetching data from all lists.[/dim]"

    panel = Panel(
        stats_text,
        title=f"{'📊 ' if icons else ''}AniList Statistics",
        border_style="green",
    )
    console.print(panel)

    feedback.pause_for_user("Press Enter to continue")
    return ControlFlow.CONTINUE


def _search_all_lists(ctx: Context, feedback, icons: bool) -> State | ControlFlow:
    """Search across all user lists."""
    try:
        query = click.prompt("Enter search query", type=str)
        if not query.strip():
            return ControlFlow.CONTINUE

        # This would require implementing search across all lists
        feedback.info(
            "Search functionality",
            "Cross-list search will be implemented in a future update",
        )
        feedback.pause_for_user("Press Enter to continue")

    except click.Abort:
        pass

    return ControlFlow.CONTINUE


def _add_anime_to_list(ctx: Context, feedback, icons: bool) -> State | ControlFlow:
    """Add a new anime to one of the user's lists."""
    try:
        query = click.prompt("Enter anime name to search", type=str)
        if not query.strip():
            return ControlFlow.CONTINUE

        # Navigate to search with intent to add to list
        return State(
            menu_name="PROVIDER_SEARCH", data={"query": query, "add_to_list_mode": True}
        )

    except click.Abort:
        pass

    return ControlFlow.CONTINUE


def _add_anime_to_specific_list(
    ctx: Context, list_status: str, feedback, icons: bool
) -> State | ControlFlow:
    """Add a new anime to a specific list."""
    try:
        query = click.prompt("Enter anime name to search", type=str)
        if not query.strip():
            return ControlFlow.CONTINUE

        # Navigate to search with specific list target
        return State(
            menu_name="PROVIDER_SEARCH",
            data={"query": query, "target_list": list_status},
        )

    except click.Abort:
        pass

    return ControlFlow.CONTINUE


def _remove_anime_from_list(
    ctx: Context,
    result: MediaSearchResult,
    list_status: str,
    page: int,
    feedback,
    icons: bool,
) -> State | ControlFlow:
    """Select and remove an anime from the current list."""
    if not result.media:
        feedback.info("Empty list", "No anime to remove from this list")
        feedback.pause_for_user("Press Enter to continue")
        return ControlFlow.CONTINUE

    # Create choices from anime list
    choices = []
    for i, anime in enumerate(result.media, 1):
        title = anime.title.english or anime.title.romaji or "Unknown Title"
        choices.append(f"{i}. {title}")

    choice = ctx.selector.choose(
        prompt="Select anime to remove",
        choices=choices,
        header="Remove Anime from List",
    )

    if not choice:
        return ControlFlow.CONTINUE

    # Extract index and get selected anime
    try:
        index = int(choice.split(".")[0]) - 1
        selected_anime = result.media[index]

        return _confirm_remove_anime(
            ctx, selected_anime, list_status, page, feedback, icons
        )
    except (ValueError, IndexError):
        return ControlFlow.CONTINUE


def _show_list_statistics(
    ctx: Context, list_status: str, feedback, icons: bool
) -> State | ControlFlow:
    """Show statistics for a specific list."""
    console = Console()
    console.clear()

    list_name = _status_to_display_name(list_status)

    stats_text = f"[bold cyan]📊 {list_name} Statistics[/bold cyan]\n\n"
    stats_text += "[dim]Loading list statistics...[/dim]\n"
    stats_text += "[dim]This feature requires comprehensive list analysis.[/dim]"

    panel = Panel(
        stats_text,
        title=f"{'📊 ' if icons else ''}{list_name} Stats",
        border_style="blue",
    )
    console.print(panel)

    feedback.pause_for_user("Press Enter to continue")
    return ControlFlow.CONTINUE


def _status_to_display_name(status: str) -> str:
    """Convert API status to human-readable display name."""
    status_map = {
        "CURRENT": "Currently Watching",
        "PLANNING": "Planning to Watch",
        "COMPLETED": "Completed",
        "PAUSED": "Paused",
        "DROPPED": "Dropped",
        "REPEATING": "Rewatching",
    }
    return status_map.get(status, status)


# Import click for user input
import click
