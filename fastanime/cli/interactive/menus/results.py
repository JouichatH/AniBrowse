from ....libs.api.params import ApiSearchParams, UserListParams
from ....libs.api.types import MediaItem
from ..session import Context, session
from ..state import ControlFlow, MediaApiState, State


@session.menu
def results(ctx: Context, state: State) -> State | ControlFlow:
    search_results = state.media_api.search_results
    feedback = ctx.services.feedback
    feedback.clear_console()

    if not search_results or not search_results.media:
        feedback.info("No anime found for the given criteria")
        return ControlFlow.BACK

    anime_items = search_results.media
    formatted_titles = [
        _format_anime_choice(anime, ctx.config) for anime in anime_items
    ]

    anime_map = dict(zip(formatted_titles, anime_items))

    preview_command = None
    if ctx.config.general.preview != "none":
        from ...utils.previews import get_anime_preview

        preview_command = get_anime_preview(anime_items, formatted_titles, ctx.config)

    choices = formatted_titles
    page_info = search_results.page_info

    # Add pagination controls if available with more descriptive text
    if page_info.has_next_page:
        choices.append(
            f"{'➡️ ' if ctx.config.general.icons else ''}Next Page (Page {page_info.current_page + 1})"
        )
    if page_info.current_page > 1:
        choices.append(
            f"{'⬅️ ' if ctx.config.general.icons else ''}Previous Page (Page {page_info.current_page - 1})"
        )
    choices.append("Back")

    # Create header with auth status and pagination info
    pagination_info = f"Page {page_info.current_page}"
    if page_info.total > 0 and page_info.per_page > 0:
        total_pages = (page_info.total + page_info.per_page - 1) // page_info.per_page
        pagination_info += f" of ~{total_pages}"

    choice_str = ctx.selector.choose(
        prompt="Select Anime",
        choices=choices,
        preview=preview_command,
    )

    if not choice_str:
        return ControlFlow.EXIT

    if choice_str == "Back":
        return ControlFlow.BACK

    if (
        choice_str == "Next Page"
        or choice_str == "Previous Page"
        or choice_str.startswith("Next Page (")
        or choice_str.startswith("Previous Page (")
    ):
        page_delta = 1 if choice_str.startswith("Next Page") else -1

        return _handle_pagination(ctx, state, page_delta)

    selected_anime = anime_map.get(choice_str)
    if selected_anime:
        return State(
            menu_name="MEDIA_ACTIONS",
            media_api=MediaApiState(
                search_results=state.media_api.search_results,  # Carry over the list
                anime=selected_anime,  # Set the newly selected item
            ),
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

    return display_title


def _handle_pagination(
    ctx: Context, state: State, page_delta: int
) -> State | ControlFlow:
    """
    Handle pagination by fetching the next or previous page of results.

    Args:
        ctx: The application context
        state: Current state containing search results and original parameters
        page_delta: +1 for next page, -1 for previous page

    Returns:
        New State with updated search results or ControlFlow.CONTINUE on error
    """
    feedback = ctx.services.feedback

    if not state.media_api.search_results:
        feedback.error("No search results available for pagination")
        return ControlFlow.CONTINUE

    current_page = state.media_api.search_results.page_info.current_page
    new_page = current_page + page_delta

    # Validate page bounds
    if new_page < 1:
        feedback.warning("Already at the first page")
        return ControlFlow.CONTINUE

    if page_delta > 0 and not state.media_api.search_results.page_info.has_next_page:
        feedback.warning("No more pages available")
        return ControlFlow.CONTINUE

    # Determine which type of search to perform based on stored parameters
    if state.media_api.original_api_params:
        # Media search (trending, popular, search, etc.)
        return _fetch_media_page(ctx, state, new_page, feedback)
    elif state.media_api.original_user_list_params:
        # User list search (watching, completed, etc.)
        return _fetch_user_list_page(ctx, state, new_page, feedback)
    else:
        feedback.error("No original search parameters found for pagination")
        return ControlFlow.CONTINUE


def _fetch_media_page(
    ctx: Context, state: State, page: int, feedback
) -> State | ControlFlow:
    """Fetch a specific page for media search results."""
    original_params = state.media_api.original_api_params
    if not original_params:
        feedback.error("No original API parameters found")
        return ControlFlow.CONTINUE

    # Create new parameters with updated page number
    new_params = ApiSearchParams(
        query=original_params.query,
        page=page,
        per_page=original_params.per_page,
        sort=original_params.sort,
        id_in=original_params.id_in,
        genre_in=original_params.genre_in,
        genre_not_in=original_params.genre_not_in,
        tag_in=original_params.tag_in,
        tag_not_in=original_params.tag_not_in,
        status_in=original_params.status_in,
        status=original_params.status,
        status_not_in=original_params.status_not_in,
        popularity_greater=original_params.popularity_greater,
        popularity_lesser=original_params.popularity_lesser,
        averageScore_greater=original_params.averageScore_greater,
        averageScore_lesser=original_params.averageScore_lesser,
        seasonYear=original_params.seasonYear,
        season=original_params.season,
        startDate_greater=original_params.startDate_greater,
        startDate_lesser=original_params.startDate_lesser,
        startDate=original_params.startDate,
        endDate_greater=original_params.endDate_greater,
        endDate_lesser=original_params.endDate_lesser,
        format_in=original_params.format_in,
        type=original_params.type,
        on_list=original_params.on_list,
    )

    result = ctx.media_api.search_media(new_params)

    return State(
        menu_name="RESULTS",
        media_api=MediaApiState(
            search_results=result,
            original_api_params=original_params,  # Keep original params for further pagination
            original_user_list_params=state.media_api.original_user_list_params,
        ),
        provider=state.provider,  # Preserve provider state if it exists
    )


def _fetch_user_list_page(
    ctx: Context, state: State, page: int, feedback
) -> State | ControlFlow:
    """Fetch a specific page for user list results."""
    original_params = state.media_api.original_user_list_params
    if not original_params:
        feedback.error("No original user list parameters found")
        return ControlFlow.CONTINUE

    # Create new parameters with updated page number
    new_params = UserListParams(
        status=original_params.status,
        page=page,
        per_page=original_params.per_page,
    )

    result = ctx.media_api.fetch_user_list(new_params)

    return State(
        menu_name="RESULTS",
        media_api=MediaApiState(
            search_results=result,
            original_api_params=state.media_api.original_api_params,
            original_user_list_params=original_params,  # Keep original params for further pagination
        ),
        provider=state.provider,  # Preserve provider state if it exists
    )
