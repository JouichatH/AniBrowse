import random
from typing import Callable, Dict, Tuple

from rich.console import Console

from ....libs.api.params import ApiSearchParams, UserListParams
from ....libs.api.types import MediaSearchResult, MediaStatus, UserListStatusType
from ...utils.feedback import create_feedback_manager, execute_with_feedback
from ...utils.auth.utils import format_auth_menu_header, check_authentication_required
from ..session import Context, session
from ..state import ControlFlow, MediaApiState, State

MenuAction = Callable[[], Tuple[str, MediaSearchResult | None, ApiSearchParams | None, UserListParams | None]]


@session.menu
def main(ctx: Context, state: State) -> State | ControlFlow:
    """
    The main entry point menu for the interactive session.
    Displays top-level categories for the user to browse and select.
    """
    icons = ctx.config.general.icons
    feedback = create_feedback_manager(icons)
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
        # --- List Management ---
        f"{'📚 ' if icons else ''}AniList Lists Manager": lambda: ("ANILIST_LISTS", None, None, None),
        f"{'📖 ' if icons else ''}Local Watch History": lambda: ("WATCH_HISTORY", None, None, None),
        # --- Authentication and Account Management ---
        f"{'🔐 ' if icons else ''}Authentication": lambda: ("AUTH", None, None, None),
        # --- Control Flow and Utility Options ---
        f"{'🔧 ' if icons else ''}Session Management": lambda: ("SESSION_MANAGEMENT", None, None, None),
        f"{'📝 ' if icons else ''}Edit Config": lambda: ("RELOAD_CONFIG", None, None, None),
        f"{'❌ ' if icons else ''}Exit": lambda: ("EXIT", None, None, None),
    }

    choice_str = ctx.selector.choose(
        prompt="Select Category",
        choices=list(options.keys()),
        header=format_auth_menu_header(ctx.media_api, "FastAnime Main Menu", icons),
    )

    if not choice_str:
        return ControlFlow.EXIT

    # --- Action Handling ---
    selected_action = options[choice_str]

    next_menu_name, result_data, api_params, user_list_params = selected_action()

    if next_menu_name == "EXIT":
        return ControlFlow.EXIT
    if next_menu_name == "RELOAD_CONFIG":
        return ControlFlow.RELOAD_CONFIG
    if next_menu_name == "SESSION_MANAGEMENT":
        return State(menu_name="SESSION_MANAGEMENT")
    if next_menu_name == "AUTH":
        return State(menu_name="AUTH")
    if next_menu_name == "ANILIST_LISTS":
        return State(menu_name="ANILIST_LISTS")
    if next_menu_name == "WATCH_HISTORY":
        return State(menu_name="WATCH_HISTORY")
    if next_menu_name == "CONTINUE":
        return ControlFlow.CONTINUE

    if not result_data:
        feedback.error(
            f"Failed to fetch data for '{choice_str.strip()}'",
            "Please check your internet connection and try again.",
        )
        return ControlFlow.CONTINUE

    # On success, transition to the RESULTS menu state.
    return State(
        menu_name="RESULTS",
        media_api=MediaApiState(
            search_results=result_data,
            original_api_params=api_params,
            original_user_list_params=user_list_params,
        ),
    )


def _create_media_list_action(
    ctx: Context, sort, status: MediaStatus | None = None
) -> MenuAction:
    """A factory to create menu actions for fetching media lists"""

    def action():
        feedback = create_feedback_manager(ctx.config.general.icons)

        # Create the search parameters
        search_params = ApiSearchParams(
            sort=sort, per_page=ctx.config.anilist.per_page, status=status
        )

        def fetch_data():
            return ctx.media_api.search_media(search_params)

        success, result = execute_with_feedback(
            fetch_data,
            feedback,
            "fetch anime list",
            loading_msg="Fetching anime",
            success_msg="Anime list loaded successfully",
        )

        # Return the search parameters along with the result for pagination
        return ("RESULTS", result, search_params, None) if success else ("CONTINUE", None, None, None)

    return action


def _create_random_media_list(ctx: Context) -> MenuAction:
    def action():
        feedback = create_feedback_manager(ctx.config.general.icons)

        # Create the search parameters
        search_params = ApiSearchParams(
            id_in=random.sample(range(1, 160000), k=50),
            per_page=ctx.config.anilist.per_page,
        )

        def fetch_data():
            return ctx.media_api.search_media(search_params)

        success, result = execute_with_feedback(
            fetch_data,
            feedback,
            "fetch random anime",
            loading_msg="Fetching random anime",
            success_msg="Random anime loaded successfully",
        )

        # Return the search parameters along with the result for pagination
        return ("RESULTS", result, search_params, None) if success else ("CONTINUE", None, None, None)

    return action


def _create_search_media_list(ctx: Context) -> MenuAction:
    def action():
        feedback = create_feedback_manager(ctx.config.general.icons)

        query = ctx.selector.ask("Search for Anime")
        if not query:
            return "CONTINUE", None, None, None

        # Create the search parameters
        search_params = ApiSearchParams(query=query)

        def fetch_data():
            return ctx.media_api.search_media(search_params)

        success, result = execute_with_feedback(
            fetch_data,
            feedback,
            "search anime",
            loading_msg=f"Searching for '{query}'",
            success_msg=f"Search results for '{query}' loaded successfully",
        )

        # Return the search parameters along with the result for pagination
        return ("RESULTS", result, search_params, None) if success else ("CONTINUE", None, None, None)

    return action


def _create_user_list_action(ctx: Context, status: UserListStatusType) -> MenuAction:
    """A factory to create menu actions for fetching user lists, handling authentication."""

    def action():
        feedback = create_feedback_manager(ctx.config.general.icons)

        # Check authentication
        if not check_authentication_required(
            ctx.media_api, feedback, f"view your {status.lower()} list"
        ):
            return "CONTINUE", None, None, None

        # Create the user list parameters
        user_list_params = UserListParams(status=status, per_page=ctx.config.anilist.per_page)

        def fetch_data():
            return ctx.media_api.fetch_user_list(user_list_params)

        success, result = execute_with_feedback(
            fetch_data,
            feedback,
            f"fetch {status.lower()} list",
            loading_msg=f"Fetching your {status.lower()} list",
            success_msg=f"Your {status.lower()} list loaded successfully",
        )

        # Return the user list parameters along with the result for pagination
        return ("RESULTS", result, None, user_list_params) if success else ("CONTINUE", None, None, None)

    return action
