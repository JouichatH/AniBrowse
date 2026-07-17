import json
import logging
import os
import threading
from typing import Dict, List

from .....core.constants import APP_CACHE_DIR
from .....core.patterns import TORRENT_REGEX
from .....libs.player.params import PlayerParams
from .....libs.provider.anime.types import Server
from ...session import Context, session
from ...state import InternalDirective, MenuName, State
from ._prefetch import get_servers, prefetch_neighbours, resolve_first

logger = logging.getLogger(__name__)


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
    #
    # Optimization A: when the preference is TOP (the default), we don't need the
    # full server list to start - just the best-ranked one. resolve_first yields
    # that first extractable server immediately and finishes resolving the rest in
    # the background during playback, so time-to-playback isn't gated on extracting
    # every source. The full list is materialized after playback (below) for the
    # in-player server-switch menu. Any other preference needs the whole list up
    # front (to match a named server or offer the selection menu), so it uses the
    # blocking full resolve.
    preferred_server = config.stream.server.value
    pending = None
    with feedback.progress("Fetching Servers"):
        if preferred_server == "TOP":
            pending = resolve_first(
                provider, config, provider_anime.id, anime_title, episode_number
            )
            all_servers = [pending.first] if pending.first else []
        else:
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

    # Write the in-player server-switch menu (Shift+S) data. We seed it with what
    # we already have (just the launched server on the Optimization-A fast path)
    # so the file exists immediately, then a background thread rewrites it with
    # the full list as resolution finishes during playback.
    servers_json = _servers_json_path()
    _write_servers_json(
        servers_json, all_servers, config.stream.quality, selected_server.name
    )
    if pending is not None:
        _current_name = selected_server.name

        def _update_servers_json() -> None:
            full = pending.result(timeout=30.0)
            if full:
                _write_servers_json(
                    servers_json, full, config.stream.quality, _current_name
                )

        threading.Thread(target=_update_servers_json, daemon=True).start()

    player_result = ctx.player.play(
        PlayerParams(
            url=stream_link_obj.link,
            title=final_title,
            servers_json=servers_json,
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

    # The rest of the server list resolved in the background while the episode
    # played (Optimization A). Materialize the full map now so the post-playback
    # "change server" menu has every option, not just the one we launched on.
    if pending is not None:
        full_servers = pending.result(timeout=5.0)
        if full_servers:
            server_map = {s.name: s for s in full_servers}

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


def _servers_json_path() -> str:
    """Stable, app-owned path the ani_skip Lua reads for the server-switch menu."""
    return str(APP_CACHE_DIR / "servers.json")


def _server_switch_entries(
    servers: List[Server], quality: str, current_name: str
) -> list[dict]:
    """Serialize servers for the Lua switch menu: one entry per switchable server.

    Each entry carries the quality-filtered URL, the server's HTTP headers and any
    external subtitles. Torrent/magnet servers are excluded — mpv cannot loadfile a
    magnet into a running instance (they need a separate webtorrent process).
    """
    entries: list[dict] = []
    for s in servers:
        link = _filter_by_quality(s.links, quality)
        if not link or not link.link or TORRENT_REGEX.match(link.link):
            continue
        entries.append(
            {
                "name": s.name,
                "url": link.link,
                "quality": str(link.quality),
                "headers": dict(s.headers or {}),
                "subtitles": [sub.url for sub in (s.subtitles or [])],
                "current": s.name == current_name,
            }
        )
    return entries


def _write_servers_json(
    path: str, servers: List[Server], quality: str, current_name: str
) -> None:
    """Atomically write the server-switch menu JSON (best-effort)."""
    entries = _server_switch_entries(servers, quality, current_name)
    try:
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(entries, fh)
        os.replace(tmp, path)
    except OSError as e:  # a disk hiccup here must never break playback
        logger.debug("could not write servers menu json: %s", e)


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
