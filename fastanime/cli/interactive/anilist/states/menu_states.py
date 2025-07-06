from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional, Tuple

from .....libs.api.base import ApiSearchParams
from .base import GoBack, State
from .task_states import AnimeActionsState

if TYPE_CHECKING:
    from .....libs.api.types import MediaSearchResult
    from ...session import Session
    from .. import ui

logger = logging.getLogger(__name__)


class MainMenuState(State):
    """Handles the main menu display and action routing."""

    def run(self, session: Session) -> Optional[State | type[GoBack]]:
        from .. import ui

        # Define actions as tuples: (Display Name, SearchParams, Next State)
        # This centralizes the "business logic" of what each menu item means.
        menu_actions: List[
            Tuple[str, Callable[[], Optional[ApiSearchParams]], Optional[State]]
        ] = [
            (
                "🔥 Trending",
                lambda: ApiSearchParams(sort="TRENDING_DESC"),
                ResultsState(),
            ),
            (
                "🌟 Most Popular",
                lambda: ApiSearchParams(sort="POPULARITY_DESC"),
                ResultsState(),
            ),
            (
                "💖 Most Favourite",
                lambda: ApiSearchParams(sort="FAVOURITES_DESC"),
                ResultsState(),
            ),
            (
                "🔎 Search",
                lambda: ApiSearchParams(query=ui.prompt_for_search(session)),
                ResultsState(),
            ),
            (
                "📺 Watching",
                lambda: session.api_client.fetch_user_list,
                ResultsState(),
            ),  # Direct method call
            ("❌ Exit", lambda: None, None),
        ]

        display_choices = [action[0] for action in menu_actions]
        choice_str = ui.prompt_main_menu(session, display_choices)

        if not choice_str:
            return None

        # Find the chosen action
        chosen_action = next(
            (action for action in menu_actions if action[0] == choice_str), None
        )
        if not chosen_action:
            return self  # Should not happen

        _, param_creator, next_state = chosen_action

        if not next_state:  # Exit case
            return None

        # Execute the data fetch
        with ui.progress_spinner(f"Fetching {choice_str.strip('🔥🔎📺🌟💖❌ ')}..."):
            if choice_str == "📺 Watching":  # Special case for user list
                result_data = param_creator(status="CURRENT")
            else:
                search_params = param_creator()
                if search_params is None:  # User cancelled search prompt
                    return self
                result_data = session.api_client.search_media(search_params)

        if not result_data:
            ui.display_error(f"Failed to fetch data for '{choice_str}'.")
            return self

        session.state.anilist.results_data = result_data  # Store the generic dataclass
        return next_state


class ResultsState(State):
    """Displays a list of anime and handles pagination and selection."""

    def run(self, session: Session) -> Optional[State | type[GoBack]]:
        from .. import ui

        search_result = session.state.anilist.results_data
        if not search_result or not isinstance(search_result, MediaSearchResult):
            ui.display_error("No results to display.")
            return GoBack

        selection = ui.prompt_anime_selection(session, search_result.media)

        if selection == "Back":
            return GoBack
        if selection is None:
            return None

        # TODO: Implement pagination logic here by checking selection for "Next Page" etc.
        # and re-calling the search_media method with an updated page number.

        session.state.anilist.selected_anime = selection
        return AnimeActionsState()
