from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from ....libs.anime.params import AnimeParams
from .base import GoBack, State

if TYPE_CHECKING:
    from ....libs.anime.types import Anime
    from ...session import Session
    from .. import actions, ui

logger = logging.getLogger(__name__)


class AnimeActionsState(State):
    """Displays actions for a single selected anime."""

    def run(self, session: Session) -> Optional[State | type[GoBack]]:
        from .. import actions, ui

        anime = session.state.anilist.selected_anime
        if not anime:
            ui.display_error("No anime selected.")
            return GoBack

        action = ui.prompt_anime_actions(session, anime)

        if not action:
            return GoBack

        if action == "Stream":
            return ProviderSearchState()
        elif action == "Watch Trailer":
            actions.play_trailer(session)
            return self
        elif action == "Add to List":
            actions.add_to_anilist(session)
            return self
        elif action == "Back":
            return GoBack

        return self


class ProviderSearchState(State):
    """Searches the provider for the selected AniList anime."""

    def run(self, session: Session) -> Optional[State | type[GoBack]]:
        from .. import actions, ui

        anime = session.state.anilist.selected_anime
        if not anime:
            return GoBack

        with ui.progress_spinner("Searching provider..."):
            best_match = actions.find_best_provider_match(session)

        if best_match:
            session.state.provider.selected_search_result = best_match
            return EpisodeSelectionState()
        else:
            title = anime.get("title", {}).get("romaji")
            ui.display_error(
                f"Could not find '{title}' on provider '{session.provider.__class__.__name__}'."
            )
            return GoBack


class EpisodeSelectionState(State):
    """Fetches the full episode list from the provider and lets the user choose."""

    def run(self, session: Session) -> Optional[State | type[GoBack]]:
        from .. import ui

        search_result = session.state.provider.selected_search_result
        if not search_result:
            return GoBack

        with ui.progress_spinner("Fetching episode list..."):
            params = AnimeParams(anime_id=search_result.id)
            anime_details: Optional[Anime] = session.provider.get(params)

        if not anime_details:
            ui.display_error("Failed to fetch episode details from provider.")
            return GoBack

        session.state.provider.anime_details = anime_details

        episode_list = (
            anime_details.episodes.sub
            if session.config.stream.translation_type == "sub"
            else anime_details.episodes.dub
        )
        if not episode_list:
            ui.display_error(
                f"No episodes of type '{session.config.stream.translation_type}' found."
            )
            return GoBack

        selected_episode = ui.prompt_episode_selection(
            session, sorted(episode_list, key=float), anime_details
        )

        if selected_episode is None:
            return GoBack

        session.state.provider.current_episode = selected_episode
        return StreamPlaybackState()


class StreamPlaybackState(State):
    """Fetches stream links for the chosen episode and initiates playback."""

    def run(self, session: Session) -> Optional[State | type[GoBack]]:
        from .. import actions, ui

        if (
            not session.state.provider.anime_details
            or not session.state.provider.current_episode
        ):
            return GoBack

        with ui.progress_spinner(
            f"Fetching streams for episode {session.state.provider.current_episode}..."
        ):
            stream_servers = actions.get_stream_links(session)

        if not stream_servers:
            ui.display_error("No streams found for this episode.")
            return GoBack

        best_link_info = actions.select_best_stream_quality(
            stream_servers, session.config.stream.quality, session
        )
        if not best_link_info:
            ui.display_error(
                f"Could not find quality '{session.config.stream.quality}p'."
            )
            return GoBack

        playback_result = actions.play_stream(session, best_link_info)

        return GoBack
