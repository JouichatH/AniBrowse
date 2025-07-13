from typing import TYPE_CHECKING, List

import click
from rich.progress import Progress
from yt_dlp.utils import sanitize_filename

from ...utils.anilist import (
    anilist_data_helper,  # Assuming this is the new location
)
from ...utils.previews import get_anime_preview
from ..session import Context, session
from ..state import ControlFlow, MediaApiState, State

if TYPE_CHECKING:
    from ....libs.api.types import MediaItem


@session.menu
def results(ctx: Context, state: State) -> State | ControlFlow:
    """
    Displays a paginated list of anime from a search or category query.
    Allows the user to select an anime to view its actions or navigate pages.
    """
    search_results = state.media_api.search_results
    if not search_results or not search_results.media:
        click.echo("[bold yellow]No anime found for the given criteria.[/bold yellow]")
        return ControlFlow.BACK

    # --- Prepare choices and previews ---
    anime_items = search_results.media
    formatted_titles = [
        _format_anime_choice(anime, ctx.config) for anime in anime_items
    ]

    # Map formatted titles back to the original MediaItem objects
    anime_map = dict(zip(formatted_titles, anime_items))

    preview_command = None
    if ctx.config.general.preview != "none":
        # This function will start background jobs to cache preview data
        preview_command = get_anime_preview(anime_items, formatted_titles, ctx.config)

    # --- Build Navigation and Final Choice List ---
    choices = formatted_titles
    page_info = search_results.page_info

    # Add pagination controls if available
    if page_info.has_next_page:
        choices.append("Next Page")
    if page_info.current_page > 1:
        choices.append("Previous Page")
    choices.append("Back")

    # --- Prompt User ---
    choice_str = ctx.selector.choose(
        prompt="Select Anime",
        choices=choices,
        header="AniList Results",
        preview=preview_command,
    )

    if not choice_str:
        return ControlFlow.EXIT

    # --- Handle User Selection ---
    if choice_str == "Back":
        return ControlFlow.BACK

    if choice_str == "Next Page" or choice_str == "Previous Page":
        page_delta = 1 if choice_str == "Next Page" else -1

        # We need to re-run the previous state's data loader with a new page.
        # This is a bit tricky. We'll need to store the loader function in the session.
        # For now, let's assume a simplified re-search. A better way will be to store the
        # search params in the State. Let's add that.

        # Let's placeholder this for now, as it requires modifying the state object
        # to carry over the original search parameters.
        click.echo(f"Pagination logic needs to be fully implemented.")
        return ControlFlow.CONTINUE

    # If an anime was selected, transition to the MEDIA_ACTIONS state
    selected_anime = anime_map.get(choice_str)
    if selected_anime:
        return State(
            menu_name="MEDIA_ACTIONS",
            media_api=MediaApiState(
                search_results=state.media_api.search_results,  # Carry over the list
                anime=selected_anime,  # Set the newly selected item
            ),
            # Persist provider state if it exists
            provider=state.provider,
        )

    # Fallback
    return ControlFlow.CONTINUE


def _format_anime_choice(anime: MediaItem, config) -> str:
    """Creates a display string for a single anime item for the selector."""
    title = anime.title.english or anime.title.romaji
    progress = "0"
    if anime.user_status:
        progress = str(anime.user_status.progress or 0)

    episodes_total = str(anime.episodes or "??")
    display_title = f"{title} ({progress} of {episodes_total})"

    # Add a visual indicator for new episodes if applicable
    if (
        anime.status == "RELEASING"
        and anime.next_airing
        and anime.user_status
        and anime.user_status.status == "CURRENT"
    ):
        last_aired = anime.next_airing.episode - 1
        unwatched = last_aired - (anime.user_status.progress or 0)
        if unwatched > 0:
            icon = "🔹" if config.general.icons else "!"
            display_title += f" {icon}{unwatched} new{icon}"

    # Sanitize for use as a potential filename/cache key
    return sanitize_filename(display_title, restricted=True)
