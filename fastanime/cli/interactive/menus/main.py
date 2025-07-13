# fastanime/cli/interactive/menus/main.py

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Callable, Dict, Tuple

import click
from rich.progress import Progress

from ....libs.api.params import ApiSearchParams, UserListParams
from ..session import Context, session
from ..state import ControlFlow, MediaApiState, State

if TYPE_CHECKING:
    from ....libs.api.types import MediaSearchResult


# A type alias for the actions this menu can perform.
# It returns a tuple: (NextMenuNameOrControlFlow, Optional[DataPayload])
MenuAction = Callable[[], Tuple[str, MediaSearchResult | None]]


@session.menu
def main(ctx: Context, state: State) -> State | ControlFlow:
    """
    The main entry point menu for the interactive session.
    Displays top-level categories for the user to browse and select.
    """
    icons = ctx.config.general.icons
    api_client = ctx.media_api
    per_page = ctx.config.anilist.per_page

    # The lambdas now correctly use the versatile search_media for most actions.
    options: Dict[str, MenuAction] = {
        # --- Search-based Actions ---
        f"{'🔥 ' if icons else ''}Trending": lambda: (
            "RESULTS",
            api_client.search_media(
                ApiSearchParams(sort="TRENDING_DESC", per_page=per_page)
            ),
        ),
        f"{'✨ ' if icons else ''}Popular": lambda: (
            "RESULTS",
            api_client.search_media(
                ApiSearchParams(sort="POPULARITY_DESC", per_page=per_page)
            ),
        ),
        f"{'💖 ' if icons else ''}Favourites": lambda: (
            "RESULTS",
            api_client.search_media(
                ApiSearchParams(sort="FAVOURITES_DESC", per_page=per_page)
            ),
        ),
        f"{'💯 ' if icons else ''}Top Scored": lambda: (
            "RESULTS",
            api_client.search_media(
                ApiSearchParams(sort="SCORE_DESC", per_page=per_page)
            ),
        ),
        f"{'🎬 ' if icons else ''}Upcoming": lambda: (
            "RESULTS",
            api_client.search_media(
                ApiSearchParams(
                    status="NOT_YET_RELEASED", sort="POPULARITY_DESC", per_page=per_page
                )
            ),
        ),
        f"{'🔔 ' if icons else ''}Recently Updated": lambda: (
            "RESULTS",
            api_client.search_media(
                ApiSearchParams(
                    status="RELEASING", sort="UPDATED_AT_DESC", per_page=per_page
                )
            ),
        ),
        f"{'🎲 ' if icons else ''}Random": lambda: (
            "RESULTS",
            api_client.search_media(
                ApiSearchParams(
                    id_in=random.sample(range(1, 160000), k=50), per_page=per_page
                )
            ),
        ),
        f"{'🔎 ' if icons else ''}Search": lambda: (
            "RESULTS",
            api_client.search_media(
                ApiSearchParams(query=ctx.selector.ask("Search for Anime"))
            ),
        ),
        # --- Authenticated User List Actions ---
        f"{'📺 ' if icons else ''}Watching": _create_user_list_action(ctx, "CURRENT"),
        f"{'📑 ' if icons else ''}Planned": _create_user_list_action(ctx, "PLANNING"),
        f"{'✅ ' if icons else ''}Completed": _create_user_list_action(
            ctx, "COMPLETED"
        ),
        f"{'⏸️ ' if icons else ''}Paused": _create_user_list_action(ctx, "PAUSED"),
        f"{'🚮 ' if icons else ''}Dropped": _create_user_list_action(ctx, "DROPPED"),
        f"{'🔁 ' if icons else ''}Rewatching": _create_user_list_action(
            ctx, "REPEATING"
        ),
        # --- Control Flow and Utility Options ---
        f"{'📝 ' if icons else ''}Edit Config": lambda: ("RELOAD_CONFIG", None),
        f"{'❌ ' if icons else ''}Exit": lambda: ("EXIT", None),
    }

    choice_str = ctx.selector.choose(
        prompt="Select Category",
        choices=list(options.keys()),
        header="FastAnime Main Menu",
    )

    if not choice_str:
        return ControlFlow.EXIT

    # --- Action Handling ---
    selected_action = options[choice_str]

    with Progress(transient=True) as progress:
        task = progress.add_task(f"[cyan]Fetching {choice_str.strip()}...", total=None)
        next_menu_name, result_data = selected_action()
        progress.update(task, completed=True)

    if next_menu_name == "EXIT":
        return ControlFlow.EXIT
    if next_menu_name == "RELOAD_CONFIG":
        return ControlFlow.RELOAD_CONFIG
    if next_menu_name == "CONTINUE":
        return ControlFlow.CONTINUE

    if not result_data:
        click.echo(
            f"[bold red]Error:[/bold red] Failed to fetch data for '{choice_str.strip()}'."
        )
        return ControlFlow.CONTINUE

    # On success, transition to the RESULTS menu state.
    return State(
        menu_name="RESULTS",
        media_api=MediaApiState(search_results=result_data),
    )


def _create_user_list_action(ctx: Context, status: str) -> MenuAction:
    """A factory to create menu actions for fetching user lists, handling authentication."""

    def action() -> Tuple[str, MediaSearchResult | None]:
        if not ctx.media_api.user_profile:
            click.echo(
                f"[bold yellow]Please log in to view your '{status.title()}' list.[/]"
            )
            return "CONTINUE", None
        return "RESULTS", ctx.media_api.fetch_user_list(
            UserListParams(status=status, per_page=ctx.config.anilist.per_page)
        )

    return action
