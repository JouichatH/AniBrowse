from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

from ....libs.anime.params import AnimeParams, EpisodeStreamsParams, SearchParams
from ....libs.anime.types import EpisodeStream, SearchResult, Server
from ....libs.players.base import PlayerResult
from ....Utility.utils import anime_title_percentage_match

if TYPE_CHECKING:
    from ...interactive.session import Session

logger = logging.getLogger(__name__)


def find_best_provider_match(session: Session) -> Optional[SearchResult]:
    """Searches the provider via session and finds the best match."""
    anime = session.state.anilist.selected_anime
    if not anime:
        return None

    title = anime.get("title", {}).get("romaji") or anime.get("title", {}).get(
        "english"
    )
    if not title:
        return None

    search_params = SearchParams(
        query=title, translation_type=session.config.stream.translation_type
    )
    search_results_data = session.provider.search(search_params)

    if not search_results_data or not search_results_data.results:
        return None

    best_match = max(
        search_results_data.results,
        key=lambda result: anime_title_percentage_match(result.title, anime),
    )
    return best_match


def get_stream_links(session: Session) -> List[Server]:
    """Fetches streams using the session's provider and state."""
    anime_details = session.state.provider.anime_details
    episode = session.state.provider.current_episode
    if not anime_details or not episode:
        return []

    params = EpisodeStreamsParams(
        anime_id=anime_details.id,
        episode=episode,
        translation_type=session.config.stream.translation_type,
    )
    stream_generator = session.provider.episode_streams(params)
    return list(stream_generator) if stream_generator else []


def select_best_stream_quality(
    servers: List[Server], quality: str, session: Session
) -> Optional[EpisodeStream]:
    """Selects the best quality stream from a list of servers."""
    from ..ui import filter_by_quality

    for server in servers:
        if server.links:
            link_info = filter_by_quality(quality, server.links)
            if link_info:
                session.state.provider.current_server = server
                return link_info
    return None


def play_stream(session: Session, stream_info: EpisodeStream) -> PlayerResult:
    """Handles media playback and updates watch history afterwards."""
    server = session.state.provider.current_server
    if not server:
        return PlayerResult()

    start_time = "0"  # TODO: Implement watch history loading

    playback_result = session.player.play(
        url=stream_info.link,
        title=server.episode_title or "FastAnime",
        headers=server.headers,
        subtitles=server.subtitles,
        start_time=start_time,
    )

    update_watch_progress(session, playback_result)
    return playback_result


def play_trailer(session: Session) -> None:
    """Plays the anime trailer using the session player."""
    anime = session.state.anilist.selected_anime
    if not anime or not anime.get("trailer"):
        from ..ui import display_error

        display_error("No trailer available for this anime.")
        return

    trailer_url = f"https://www.youtube.com/watch?v={anime['trailer']['id']}"
    session.player.play(url=trailer_url, title=f"{anime['title']['romaji']} - Trailer")


def view_anime_info(session: Session) -> None:
    """Delegates the display of detailed anime info to the UI layer."""
    from ..ui import display_anime_details

    anime = session.state.anilist.selected_anime
    if anime:
        display_anime_details(anime)


def add_to_anilist(session: Session) -> None:
    """Prompts user for a list and adds the anime to it on AniList."""
    from ..ui import display_error, prompt_add_to_list

    if not session.config.user:
        display_error("You must be logged in to modify your AniList.")
        return

    anime = session.state.anilist.selected_anime
    if not anime:
        return

    list_status = prompt_add_to_list(session)
    if not list_status:
        return

    success, data = session.anilist.update_anime_list(
        {"status": list_status, "mediaId": anime["id"]}
    )
    if not success:
        display_error(f"Failed to update AniList. Reason: {data}")


def update_watch_progress(session: Session, playback_result: PlayerResult) -> None:
    """Updates local and remote watch history based on playback result."""
    from ....core.utils import time_to_seconds

    stop_time_str = playback_result.stop_time
    total_time_str = playback_result.total_time
    anime = session.state.anilist.selected_anime
    episode_num = session.state.provider.current_episode

    if not all([stop_time_str, total_time_str, anime, episode_num]):
        logger.debug("Insufficient data to update watch progress.")
        return

    try:
        stop_seconds = time_to_seconds(stop_time_str)
        total_seconds = time_to_seconds(total_time_str)

        # Avoid division by zero
        if total_seconds == 0:
            return

        percentage_watched = (stop_seconds / total_seconds) * 100

        # TODO: Implement local watch history file update here

        if percentage_watched >= session.config.stream.episode_complete_at:
            logger.info(
                f"Episode {episode_num} marked as complete ({percentage_watched:.1f}% watched)."
            )

            if session.config.user and session.state.tracking.progress_mode == "track":
                logger.info(
                    f"Updating AniList progress for mediaId {anime['id']} to episode {episode_num}."
                )
                session.anilist.update_anime_list(
                    {"mediaId": anime["id"], "progress": int(episode_num)}
                )

    except (ValueError, TypeError) as e:
        logger.error(f"Could not parse playback times to update progress: {e}")
