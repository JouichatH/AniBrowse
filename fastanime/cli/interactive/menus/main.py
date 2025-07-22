import logging
import random
from typing import Callable, Dict, Tuple

from ....libs.api.params import ApiSearchParams, UserListParams
from ....libs.api.types import MediaSearchResult, MediaStatus, UserListStatusType
from ..session import Context, session
from ..state import ControlFlow, MediaApiState, State

logger = logging.getLogger(__name__)
MenuAction = Callable[
    [],
    Tuple[str, MediaSearchResult | None, ApiSearchParams | None, UserListParams | None],
]


@session.menu
def main(ctx: Context, state: State) -> State | ControlFlow:
    """
    The main entry point menu for the interactive session.
    Displays top-level categories for the user to browse and select.
    """
    icons = ctx.config.general.icons
    feedback = ctx.services.feedback
    feedback.clear_console()

    # TODO: Make them just return the modified state or control flow
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
        f"{'📺 ' if icons else ''}Watching": _create_user_list_action(ctx, "watching"),
        f"{'📑 ' if icons else ''}Planned": _create_user_list_action(ctx, "planning"),
        f"{'✅ ' if icons else ''}Completed": _create_user_list_action(
            ctx, "completed"
        ),
        f"{'⏸️ ' if icons else ''}Paused": _create_user_list_action(ctx, "paused"),
        f"{'🚮 ' if icons else ''}Dropped": _create_user_list_action(ctx, "dropped"),
        f"{'🔁 ' if icons else ''}Rewatching": _create_user_list_action(
            ctx, "repeating"
        ),
        f"{'🔁 ' if icons else ''}Recent": lambda: (
            "RESULTS",
            ctx.services.media_registry.get_recently_watched(
                ctx.config.anilist.per_page
            ),
            None,
            None,
        ),
        f"{'📝 ' if icons else ''}Edit Config": lambda: (
            "CONFIG_EDIT",
            None,
            None,
            None,
        ),
        f"{'❌ ' if icons else ''}Exit": lambda: ("EXIT", None, None, None),
    }

    choice_str = ctx.selector.choose(
        prompt="Select Category",
        choices=list(options.keys()),
    )

    if not choice_str:
        return ControlFlow.EXIT

    # --- Action Handling ---
    selected_action = options[choice_str]

    next_menu_name, result_data, api_params, user_list_params = selected_action()

    if next_menu_name == "EXIT":
        return ControlFlow.EXIT
    if next_menu_name == "CONFIG_EDIT":
        return ControlFlow.CONFIG_EDIT
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
        # Create the search parameters
        search_params = ApiSearchParams(sort=sort, status=status)

        result = ctx.media_api.search_media(search_params)

        return ("RESULTS", result, search_params, None)

    return action


def _create_random_media_list(ctx: Context) -> MenuAction:
    def action():
        search_params = ApiSearchParams(id_in=random.sample(range(1, 15000), k=50))

        result = ctx.media_api.search_media(search_params)

        return ("RESULTS", result, search_params, None)

    return action


def _create_search_media_list(ctx: Context) -> MenuAction:
    def action():
        query = ctx.selector.ask("Search for Anime")
        if not query:
            return "CONTINUE", None, None, None

        search_params = ApiSearchParams(query=query)
        result = ctx.media_api.search_media(search_params)

        return ("RESULTS", result, search_params, None)

    return action


def _create_user_list_action(ctx: Context, status: UserListStatusType) -> MenuAction:
    """A factory to create menu actions for fetching user lists, handling authentication."""

    def action():
        # Check authentication
        if not ctx.media_api.is_authenticated():
            logger.warning("Not authenticated")
            return "CONTINUE", None, None, None

        user_list_params = UserListParams(status=status)

        result = ctx.media_api.search_media_list(user_list_params)

        return ("RESULTS", result, None, user_list_params)

    return action
