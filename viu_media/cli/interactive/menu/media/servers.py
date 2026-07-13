from typing import Dict

from .....libs.player.params import PlayerParams
from .....libs.provider.anime.types import Server
from ...session import Context, session
from ...state import InternalDirective, MenuName, State
from ._prefetch import get_servers, prefetch_neighbours


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

    # Resolve this episode's servers - instant if a prefetch worker already
    # warmed the cache while the previous episode played, otherwise a live fetch
    # (primary provider, then the nyaa torrent fallback for lagging simulcasts).
    with feedback.progress("Fetching Servers"):
        all_servers = get_servers(
            provider, config, provider_anime.id, anime_title, episode_number
        )

    if not all_servers:
        feedback.error(f"No streaming servers found for episode {episode_number}")
        return InternalDirective.BACKX3

    if all_servers[0].name.startswith("nyaa:"):
        feedback.info("Streaming from nyaa (torrent). Requires webtorrent-cli.")

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

    # State the source/connection clearly so it can be reviewed before playing.
    feedback.info(
        f"[bold cyan]Source:[/] {_source_summary(ctx, selected_server, stream_link_obj.link)}"
    )
    feedback.info(f"[bold green]Launching player for:[/] {final_title}")

    if not state.media_api.media_item or not state.provider.anime:
        return InternalDirective.BACKX3

    # Warm the next/previous episode's servers in the background while this
    # episode plays, so advancing is instant instead of re-fetching each time.
    prefetch_neighbours(provider, config, provider_anime, anime_title, episode_number)

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

    # In-player Shift+N / Shift+P (clean path): jump straight to the neighbour
    # episode's servers instead of showing the post-playback menu.
    if player_result.action in ("next", "previous"):
        target = _neighbour_episode(
            provider_anime, config.stream.translation_type, episode_number,
            player_result.action,
        )
        if target:
            return State(
                menu_name=MenuName.SERVERS,
                media_api=state.media_api,
                provider=state.provider.model_copy(update={"episode_": target}),
            )

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


def _stream_host(url: str) -> str:
    """Host of a stream URL (or "torrent" for a magnet) - the connection endpoint."""
    if url.startswith("magnet:") or url.endswith(".torrent"):
        return "torrent/webtorrent"
    from urllib.parse import urlparse

    try:
        return urlparse(url).hostname or "?"
    except ValueError:
        return "?"


def _source_summary(ctx, server, url: str) -> str:
    """One-line source description: provider, server, quality/type, host."""
    config = ctx.config
    is_nyaa = server.name.startswith("nyaa:")
    provider = "nyaa (torrent)" if is_nyaa else config.general.provider.value
    return (
        f"{provider} · server '{server.name}' · "
        f"{config.stream.quality}p {config.stream.translation_type} · "
        f"{_stream_host(url)}"
    )


def _neighbour_episode(
    provider_anime, translation_type: str, current: str, direction: str
) -> str | None:
    """The next/previous episode number, or None if there isn't one.

    Mirrors the fetch task's logic: step within the provider's list, and for
    "next" past the last known episode fall through to the numeric next (the
    nyaa fallback then serves it).
    """
    available = list(getattr(provider_anime.episodes, translation_type, []) or [])
    if current in available:
        idx = available.index(current)
        if direction == "next":
            if idx < len(available) - 1:
                return available[idx + 1]
        elif idx > 0:
            return available[idx - 1]
    if direction == "next":
        try:
            return str(int(float(current)) + 1)
        except (TypeError, ValueError):
            return None
    return None


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
