from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from .base import GoBack, State
from .task_states import (
    AnimeActionsState,
    EpisodeSelectionState,
    ProviderSearchState,
    StreamPlaybackState,
)

if TYPE_CHECKING:
    from ...session import Session
    from .. import ui

logger = logging.getLogger(__name__)


class MainMenuState(State):
    """Handles the main menu display and action routing."""

    def run(self, session: Session) -> Optional[State | type[GoBack]]:
        from .. import ui

        menu_actions = {
            "🔥 Trending": (session.anilist.get_trending, ResultsState()),
            "🔎 Search": (
                lambda: session.anilist.search(query=ui.prompt_for_search(session)),
                ResultsState(),
            ),
            "📺 Watching": (
                lambda: session.anilist.get_anime_list("CURRENT"),
                ResultsState(),
            ),
            "🌟 Most Popular": (session.anilist.get_most_popular, ResultsState()),
            "💖 Most Favourite": (session.anilist.get_most_favourite, ResultsState()),
            "❌ Exit": (lambda: (True, None), None),
        }

        choice = ui.prompt_main_menu(session, list(menu_actions.keys()))

        if not choice:
            return None

        data_loader, next_state = menu_actions[choice]
        if not next_state:
            return None

        with ui.progress_spinner(f"Fetching {choice.strip('🔥🔎📺🌟💖❌ ')}..."):
            success, data = data_loader()

        if not success or not data:
            ui.display_error(f"Failed to fetch data. Reason: {data}")
            return self

        if "mediaList" in data.get("data", {}).get("Page", {}):
            data["data"]["Page"]["media"] = [
                item["media"] for item in data["data"]["Page"]["mediaList"]
            ]

        session.state.anilist.results_data = data
        session.state.navigation.current_page = 1
        # Store the data loader for pagination
        session.current_data_loader = data_loader
        return next_state


class ResultsState(State):
    """Displays a list of anime and handles pagination and selection."""

    def run(self, session: Session) -> Optional[State | type[GoBack]]:
        from .. import ui

        if not session.state.anilist.results_data:
            ui.display_error("No results to display.")
            return GoBack

        media_list = (
            session.state.anilist.results_data.get("data", {})
            .get("Page", {})
            .get("media", [])
        )
        selection = ui.prompt_anime_selection(session, media_list)

        if selection == "Back":
            return GoBack
        if selection is None:
            return None  # User cancelled prompt

        if selection == "Next Page":
            page_info = (
                session.state.anilist.results_data.get("data", {})
                .get("Page", {})
                .get("pageInfo", {})
            )
            if page_info.get("hasNextPage"):
                session.state.navigation.current_page += 1
                with ui.progress_spinner("Fetching next page..."):
                    success, data = session.current_data_loader(
                        page=session.state.navigation.current_page
                    )
                if success:
                    session.state.anilist.results_data = data
                else:
                    ui.display_error("Failed to fetch next page.")
                    session.state.navigation.current_page -= 1
            else:
                ui.display_error("Already on the last page.")
            return self  # Return to the same results state

        if selection == "Previous Page":
            if session.state.navigation.current_page > 1:
                session.state.navigation.current_page -= 1
                with ui.progress_spinner("Fetching previous page..."):
                    success, data = session.current_data_loader(
                        page=session.state.navigation.current_page
                    )
                if success:
                    session.state.anilist.results_data = data
                else:
                    ui.display_error("Failed to fetch previous page.")
                    session.state.navigation.current_page += 1
            else:
                ui.display_error("Already on the first page.")
            return self

        # If it's a valid anime object
        session.state.anilist.selected_anime = selection
        return AnimeActionsState()
