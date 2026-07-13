from typing import Dict, List

from .....libs.player.params import PlayerParams
from .....libs.provider.anime.params import EpisodeStreamsParams
from .....libs.provider.anime.types import ProviderServer, Server
from ...session import Context, session
from ...state import InternalDirective, MenuName, State


@session.menu
def servers(ctx: Context, state: State) -> State | InternalDirective:
    feedback = ctx.feedback

    config = ctx.config
    provider = ctx.provider
    selector = ctx.selector

    provider_anime = state.provider.anime
    media_item = state.media_api.media_item

    anime_title = media_item.title.romaji or media_item.title.english
    episode_number = state.provider.episode

    if not provider_anime or not episode_number:
        feedback.error("Anime or episode details are missing")
        return InternalDirective.BACK

    with feedback.progress("Fetching Servers"):
        server_iterator = provider.episode_streams(
            EpisodeStreamsParams(
                anime_id=provider_anime.id,
                query=anime_title,
                episode=episode_number,
                translation_type=config.stream.translation_type,
            )
        )
        # Consume the iterator to get a list of all servers
        if config.stream.server == ProviderServer.TOP and server_iterator:
            try:
                all_servers = [next(server_iterator)]
            except Exception:
                all_servers = []
        else:
            all_servers: List[Server] = list(server_iterator) if server_iterator else []

    # Fallback: the active source has no stream for this episode (it lags behind
    # the broadcast, or extraction failed). Try nyaa torrents, which carry the
    # fastest English releases and stream via webtorrent -> mpv.
    if (
        not all_servers
        and getattr(config.stream, "nyaa_fallback", True)
        and type(provider).__name__ != "Nyaa"
    ):
        from ._source_fallback import nyaa_servers

        with feedback.progress(f"Source lacks episode {episode_number} — trying nyaa"):
            all_servers = nyaa_servers(
                anime_title,
                episode_number,
                config.stream.translation_type,
                config.stream.quality,
            )
        if all_servers:
            feedback.info("Streaming from nyaa (torrent). Requires webtorrent-cli.")

    if not all_servers:
        feedback.error(f"No streaming servers found for episode {episode_number}")
        return InternalDirective.BACKX3

    server_map: Dict[str, Server] = {s.name: s for s in all_servers}
    selected_server: Server | None = None

    preferred_server = config.stream.server.value
    if preferred_server == "TOP":
        selected_server = all_servers[0]
        feedback.info(f"Auto-selecting top server: {selected_server.name}")
    elif preferred_server in server_map:
        selected_server = server_map[preferred_server]
        feedback.info(f"Auto-selecting preferred server: {selected_server.name}")
    else:
        choices = [*server_map.keys(), "Back"]
        chosen_name = selector.choose("Select Server", choices)
        if not chosen_name or chosen_name == "Back":
            return InternalDirective.BACK
        selected_server = server_map[chosen_name]

    stream_link_obj = _filter_by_quality(selected_server.links, config.stream.quality)
    if not stream_link_obj:
        feedback.error(
            f"No stream of quality '{config.stream.quality}' found on server '{selected_server.name}'."
        )
        return InternalDirective.RELOAD

    final_title = (
        media_item.streaming_episodes[episode_number].title
        if media_item.streaming_episodes.get(episode_number)
        else f"{media_item.title.english}; Episode {episode_number}"
    )
    feedback.info(f"[bold green]Launching player for:[/] {final_title}")

    if not state.media_api.media_item or not state.provider.anime:
        return InternalDirective.BACKX3
    player_result = ctx.player.play(
        PlayerParams(
            url=stream_link_obj.link,
            title=final_title,
            query=(
                state.media_api.media_item.title.romaji
                or state.media_api.media_item.title.english
            ),
            episode=episode_number,
            subtitles=[sub.url for sub in selected_server.subtitles],
            headers=selected_server.headers,
            start_time=state.provider.start_time,
        ),
        state.provider.anime,
        state.media_api.media_item,
    )
    if media_item and episode_number:
        ctx.watch_history.track(media_item, player_result)

    # Did the video actually reach its end? Only then should auto-next fire.
    # A manual quit partway through (or a corrupt stream that exits instantly)
    # must NOT auto-advance. This is deliberately stricter than the watch-history
    # "complete" threshold: auto-next happens at the end of the video, not at 80%.
    reached_end = _reached_video_end(player_result)

    return State(
        menu_name=MenuName.PLAYER_CONTROLS,
        media_api=state.media_api,
        provider=state.provider.model_copy(
            update={
                "servers_": server_map,
                "server_name_": selected_server.name,
                "reached_end_": reached_end,
            }
        ),
    )


def _hms_to_seconds(t: str | None) -> float:
    """Parse an "HH:MM:SS" (or "MM:SS") timestamp into seconds; 0.0 if unparseable."""
    if not t:
        return 0.0
    try:
        parts = [float(p) for p in t.strip().split(":")]
    except ValueError:
        return 0.0
    seconds = 0.0
    for p in parts:
        seconds = seconds * 60 + p
    return seconds


def _reached_video_end(player_result, end_threshold_percent: float = 98.0) -> bool:
    """True if playback reached (essentially) the end of the video.

    Used to gate auto-next so it fires only at the true end of the episode - after
    any post-ending scenes - rather than at the watch-history completion threshold.
    """
    if not player_result:
        return False
    total = _hms_to_seconds(getattr(player_result, "total_time", None))
    stop = _hms_to_seconds(getattr(player_result, "stop_time", None))
    if total <= 0:
        return False
    return (stop / total) * 100 >= end_threshold_percent


def _filter_by_quality(links, quality):
    # Simplified version of your filter_by_quality for brevity
    for link in links:
        if str(link.quality) == quality:
            return link
    return links[0] if links else None
