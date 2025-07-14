import random
from typing import Callable, Dict, Tuple

from rich.console import Console
from rich.progress import Progress

from ....libs.api.params import ApiSearchParams, UserListParams
from ....libs.api.types import MediaSearchResult, MediaStatus, UserListStatusType
from ..session import Context, session
from ..state import ControlFlow, MediaApiState, State

MenuAction = Callable[[], Tuple[str, MediaSearchResult | None]]


@session.menu
def main(ctx: Context, state: State) -> State | ControlFlow:
    """
    The main entry point menu for the interactive session.
    Displays top-level categories for the user to browse and select.
    """
    icons = ctx.config.general.icons
    console = Console()
    console.clear()

    options: Dict[str, MenuAction] = {
        # --- Search-based Actions ---
        f"{'🔥 ' if icons else ''}Trending": _create_media_list_action(
            ctx, "TRENDING_DESC"
        ),
        f"{'✨ ' if icons else ''}Popular": _create_media_list_action(
            ctx, "POPULARITY_DESC"
        ),
        f"{'💖 ' if icons else ''}Favourites": _create_media_list_action(
            ctx, "FAVOURITES_DESC"
        ),
        f"{'💯 ' if icons else ''}Top Scored": _create_media_list_action(
            ctx, "SCORE_DESC"
        ),
        f"{'🎬 ' if icons else ''}Upcoming": _create_media_list_action(
            ctx, "POPULARITY_DESC", "NOT_YET_RELEASED"
        ),
        f"{'🔔 ' if icons else ''}Recently Updated": _create_media_list_action(
            ctx, "UPDATED_AT_DESC"
        ),
        # --- special case media list --
        f"{'🎲 ' if icons else ''}Random": _create_random_media_list(ctx),
        f"{'🔎 ' if icons else ''}Search": _create_search_media_list(ctx),
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

    next_menu_name, result_data = selected_action()

    if next_menu_name == "EXIT":
        return ControlFlow.EXIT
    if next_menu_name == "RELOAD_CONFIG":
        return ControlFlow.RELOAD_CONFIG
    if next_menu_name == "CONTINUE":
        return ControlFlow.CONTINUE

    if not result_data:
        console.print(
            f"[bold red]Error:[/bold red] Failed to fetch data for '{choice_str.strip()}'."
        )
        return ControlFlow.CONTINUE

    # On success, transition to the RESULTS menu state.
    return State(
        menu_name="RESULTS",
        media_api=MediaApiState(search_results=result_data),
    )


def _create_media_list_action(
    ctx: Context, sort, status: MediaStatus | None = None
) -> MenuAction:
    """A factory to create menu actions for fetching media lists"""

    def action():
        with Progress(transient=True) as progress:
            progress.add_task(f"[cyan]Fetching anime...", total=None)
            return "RESULTS", ctx.media_api.search_media(
                ApiSearchParams(
                    sort=sort, per_page=ctx.config.anilist.per_page, status=status
                )
            )

    return action


def _create_random_media_list(ctx: Context) -> MenuAction:
    def action():
        with Progress(transient=True) as progress:
            progress.add_task(f"[cyan]Fetching random anime...", total=None)
            return "RESULTS", ctx.media_api.search_media(
                ApiSearchParams(
                    id_in=random.sample(range(1, 160000), k=50),
                    per_page=ctx.config.anilist.per_page,
                )
            )

    return action


def _create_search_media_list(ctx: Context) -> MenuAction:
    def action():
        query = ctx.selector.ask("Search for Anime")
        if not query:
            return "CONTINUE", None
        with Progress(transient=True) as progress:
            progress.add_task(f"[cyan]Searching for {query}...", total=None)
            return "RESULTS", ctx.media_api.search_media(ApiSearchParams(query=query))

    return action


def _create_user_list_action(ctx: Context, status: UserListStatusType) -> MenuAction:
    """A factory to create menu actions for fetching user lists, handling authentication."""

    def action():
        # if not ctx.media_api.user_profile:
        #     click.echo(
        #         f"[bold yellow]Please log in to view your '{status.title()}' list.[/]"
        #     )
        #     return "CONTINUE", None
        with Progress(transient=True) as progress:
            progress.add_task(f"[cyan]Fetching random anime...", total=None)
            return "RESULTS", ctx.media_api.fetch_user_list(
                UserListParams(status=status, per_page=ctx.config.anilist.per_page)
            )

    return action
