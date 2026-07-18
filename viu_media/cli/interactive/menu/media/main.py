import logging
import random
from typing import Callable, Dict

from .....libs.media_api.params import MediaSearchParams, UserMediaListSearchParams
from .....libs.media_api.types import (
    MediaSort,
    MediaStatus,
    UserMediaListStatus,
)
from ...session import Context, session
from ...state import InternalDirective, MediaApiState, MenuName, State
from ._cursor import remembered_choose

logger = logging.getLogger(__name__)
MenuAction = Callable[[], State | InternalDirective]


@session.menu
def main(ctx: Context, state: State) -> State | InternalDirective:
    icons = ctx.config.general.icons
    feedback = ctx.feedback
    feedback.clear_console()

    # The personal lists work without a login: they read the on-disk registry
    # and only use AniList when authenticated. The label says which mode the
    # user is in instead of erroring "You haven't logged in" after the fact.
    local = "" if ctx.media_api.is_authenticated() else " (Local)"

    options: Dict[str, MenuAction] = {
        f"{'▶️ ' if icons else ''}Continue Watching": _create_recent_media_action(
            ctx, state
        ),
        f"{'📺 ' if icons else ''}Watching{local}": _create_user_list_action(
            ctx, state, UserMediaListStatus.WATCHING
        ),
        f"{'💛 ' if icons else ''}My Favorites": _create_favorites_action(ctx, state),
        f"{'🔥 ' if icons else ''}Trending": _create_media_list_action(
            ctx, state, MediaSort.TRENDING_DESC
        ),
        f"{'🔎 ' if icons else ''}Search": _create_search_media_list(ctx, state),
        f"{'🔍 ' if icons else ''}Dynamic Search": _create_dynamic_search_action(
            ctx, state
        ),
        f"{'🔁 ' if icons else ''}Rewatching{local}": _create_user_list_action(
            ctx, state, UserMediaListStatus.REPEATING
        ),
        f"{'⏸️ ' if icons else ''}Paused{local}": _create_user_list_action(
            ctx, state, UserMediaListStatus.PAUSED
        ),
        f"{'📑 ' if icons else ''}Planned{local}": _create_user_list_action(
            ctx, state, UserMediaListStatus.PLANNING
        ),
        f"{'🏠 ' if icons else ''}Downloads": _create_downloads_action(ctx, state),
        f"{'🔔 ' if icons else ''}Recently Updated": _create_media_list_action(
            ctx, state, MediaSort.UPDATED_AT_DESC
        ),
        f"{'✨ ' if icons else ''}Popular": _create_media_list_action(
            ctx, state, MediaSort.POPULARITY_DESC
        ),
        f"{'💯 ' if icons else ''}Top Scored": _create_media_list_action(
            ctx, state, MediaSort.SCORE_DESC
        ),
        f"{'💖 ' if icons else ''}Favourites": _create_media_list_action(
            ctx, state, MediaSort.FAVOURITES_DESC
        ),
        f"{'🎲 ' if icons else ''}Random": _create_random_media_list(ctx, state),
        f"{'🎬 ' if icons else ''}Upcoming": _create_media_list_action(
            ctx, state, MediaSort.POPULARITY_DESC, MediaStatus.NOT_YET_RELEASED
        ),
        f"{'✅ ' if icons else ''}Completed{local}": _create_user_list_action(
            ctx, state, UserMediaListStatus.COMPLETED
        ),
        f"{'🚮 ' if icons else ''}Dropped{local}": _create_user_list_action(
            ctx, state, UserMediaListStatus.DROPPED
        ),
        f"{'📝 ' if icons else ''}Edit Config": lambda: InternalDirective.CONFIG_EDIT,
        f"{'❌ ' if icons else ''}Exit": lambda: InternalDirective.EXIT,
    }

    choice = remembered_choose(
        ctx.selector,
        "main",
        prompt="Select Category",
        choices=list(options.keys()),
    )
    if not choice:
        return InternalDirective.MAIN

    selected_action = options[choice]

    next_step = selected_action()
    return next_step


def _create_media_list_action(
    ctx: Context, state: State, sort: MediaSort, status: MediaStatus | None = None
) -> MenuAction:
    def action():
        feedback = ctx.feedback
        search_params = MediaSearchParams(sort=sort, status=status)

        loading_message = "Fetching media list"
        result = None
        with feedback.progress(loading_message):
            result = ctx.media_api.search_media(search_params)

        if result:
            return State(
                menu_name=MenuName.RESULTS,
                media_api=MediaApiState(
                    search_result={
                        media_item.id: media_item for media_item in result.media
                    },
                    search_params=search_params,
                    page_info=result.page_info,
                ),
            )
        else:
            return InternalDirective.MAIN

    return action


def _create_random_media_list(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = ctx.feedback
        search_params = MediaSearchParams(id_in=random.sample(range(1, 15000), k=50))

        loading_message = "Fetching media list"
        result = None
        with feedback.progress(loading_message):
            result = ctx.media_api.search_media(search_params)

        if result:
            return State(
                menu_name=MenuName.RESULTS,
                media_api=MediaApiState(
                    search_result={
                        media_item.id: media_item for media_item in result.media
                    },
                    search_params=search_params,
                    page_info=result.page_info,
                ),
            )
        else:
            return InternalDirective.MAIN

    return action


def _create_search_media_list(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = ctx.feedback

        query = ctx.selector.ask("Search for Anime")
        if not query:
            return InternalDirective.MAIN

        search_params = MediaSearchParams(query=query)

        loading_message = "Fetching media list"
        result = None
        with feedback.progress(loading_message):
            result = ctx.media_api.search_media(search_params)

        if result:
            return State(
                menu_name=MenuName.RESULTS,
                media_api=MediaApiState(
                    search_result={
                        media_item.id: media_item for media_item in result.media
                    },
                    search_params=search_params,
                    page_info=result.page_info,
                ),
            )
        else:
            return InternalDirective.MAIN

    return action


def _create_user_list_action(
    ctx: Context, state: State, status: UserMediaListStatus
) -> MenuAction:
    """Personal list, local-first.

    Authenticated: the AniList list. Not authenticated: the same list from the
    on-disk registry (updated by watching and by Add/Update List), so personal
    lists work fully offline instead of erroring "You haven't logged in".
    """

    def action():
        feedback = ctx.feedback

        if not ctx.media_api.is_authenticated():
            result = None
            with feedback.progress(f"Getting your local {status.value} list"):
                result = ctx.media_registry.get_media_by_status(status)
            if result and result.media:
                return State(
                    menu_name=MenuName.RESULTS,
                    media_api=MediaApiState(
                        search_result={
                            media_item.id: media_item for media_item in result.media
                        },
                        page_info=result.page_info,
                    ),
                )
            feedback.info(
                f"Your local {status.value} list is empty",
                "Watch something or use Add/Update List on a show to fill it. "
                "Log in to use your AniList lists instead.",
            )
            return InternalDirective.MAIN

        search_params = UserMediaListSearchParams(status=status)

        loading_message = "Fetching media list"
        result = None
        with feedback.progress(loading_message):
            result = ctx.media_api.search_media_list(search_params)

        if result:
            return State(
                menu_name=MenuName.RESULTS,
                media_api=MediaApiState(
                    search_result={
                        media_item.id: media_item for media_item in result.media
                    },
                    search_params=search_params,
                    page_info=result.page_info,
                ),
            )
        else:
            return InternalDirective.MAIN

    return action


def _create_recent_media_action(ctx: Context, state: State) -> MenuAction:
    """Continue Watching: everything you've watched, most recent first.

    Purely local (the registry tracks progress as you watch), so it works
    without a login; each entry shows "(watched of total)" in the list.
    """

    def action():
        result = ctx.media_registry.get_recently_watched()
        if result and result.media:
            return State(
                menu_name=MenuName.RESULTS,
                media_api=MediaApiState(
                    search_result={
                        media_item.id: media_item for media_item in result.media
                    },
                    page_info=result.page_info,
                ),
            )
        ctx.feedback.info(
            "Nothing to continue yet",
            "Shows you watch land here automatically, newest first.",
        )
        return InternalDirective.MAIN

    return action


def _create_favorites_action(ctx: Context, state: State) -> MenuAction:
    """Locally-favorited shows (the heart toggle on a show's actions menu)."""

    def action():
        result = ctx.media_registry.get_favorites()
        if result and result.media:
            return State(
                menu_name=MenuName.RESULTS,
                media_api=MediaApiState(
                    search_result={
                        media_item.id: media_item for media_item in result.media
                    },
                    page_info=result.page_info,
                ),
            )
        ctx.feedback.info(
            "No favorites yet",
            "Open a show and pick 'Add to Favorites' - no login needed.",
        )
        return InternalDirective.MAIN

    return action


def _create_downloads_action(ctx: Context, state: State) -> MenuAction:
    """Create action to navigate to the downloads menu."""

    def action():
        return State(menu_name=MenuName.DOWNLOADS)

    return action


def _create_dynamic_search_action(ctx: Context, state: State) -> MenuAction:
    """Create action to navigate to the dynamic search menu."""

    def action():
        return State(menu_name=MenuName.DYNAMIC_SEARCH)

    return action
