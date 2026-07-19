"""Server resolution with background prefetch of neighbouring episodes.

In the clean (non-IPC) playback model each episode is a fresh mpv, and the
next episode's streams are resolved by the servers menu. Resolving them from
scratch each time adds a visible "Fetching Servers" delay between episodes.

While the current episode plays (a blocking mpv subprocess), we prefetch the
next/previous episode's servers into a small in-process cache; the servers menu
then consumes that cache instantly. Everything is best-effort - a prefetch miss
just means a normal fetch.

The cache is read by *peeking*, not popping: re-entering the servers menu for the
SAME episode (Replay, or Change-Server-then-Replay) reuses the already-resolved
list instead of re-fetching it (~1.7s each time). Entries carry a timestamp and
expire after ``_TTL`` so a stale stream URL is eventually re-resolved; the TTL is
comfortably longer than a typical episode so a neighbour prefetched at play-start
is still valid when the episode ends and you advance.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, List, Optional, Tuple

from .....libs.provider.anime.params import EpisodeStreamsParams
from .....libs.provider.anime.types import Server

logger = logging.getLogger(__name__)

# key -> (monotonic timestamp, servers). Timestamped so entries can expire.
_CACHE: Dict[Tuple, Tuple[float, List[Server]]] = {}
_INFLIGHT: set = set()
_LOCK = threading.Lock()
_MAX_CACHE = 8
# How long a resolved server list stays reusable. Longer than a typical episode
# (so play-start neighbour prefetches survive until you advance), but bounded so
# an expired stream URL is eventually refetched rather than replayed dead.
_TTL = 1800.0  # 30 minutes


def _key(anime_id: str, episode: str, translation_type: str) -> Tuple:
    return (anime_id, episode, translation_type)


def _cache_get(key: Tuple) -> Optional[List[Server]]:
    """Return cached servers for ``key`` without removing them, or None if absent
    or expired. Expired entries are pruned."""
    with _LOCK:
        entry = _CACHE.get(key)
        if entry is None:
            return None
        ts, servers = entry
        if time.monotonic() - ts > _TTL:
            del _CACHE[key]
            return None
        return servers


def _cache_put(key: Tuple, servers: List[Server]) -> None:
    """Store ``servers`` for ``key`` with the current timestamp, evicting the
    oldest entry when the cache is full."""
    with _LOCK:
        if key not in _CACHE and len(_CACHE) >= _MAX_CACHE:
            oldest = min(_CACHE, key=lambda k: _CACHE[k][0])
            del _CACHE[oldest]
        _CACHE[key] = (time.monotonic(), servers)


def _numeric_next(episode: str) -> Optional[str]:
    try:
        return str(int(float(episode)) + 1)
    except (TypeError, ValueError):
        return None


def _numeric_prev(episode: str) -> Optional[str]:
    try:
        n = int(float(episode)) - 1
        return str(n) if n >= 1 else None
    except (TypeError, ValueError):
        return None


def neighbour_episodes(anime, translation_type: str, current: str) -> List[str]:
    """Next and previous episode numbers around ``current`` (for prefetching)."""
    available = list(getattr(anime.episodes, translation_type, []) or [])
    targets: List[str] = []
    if current in available:
        idx = available.index(current)
        if idx < len(available) - 1:
            targets.append(available[idx + 1])
        else:
            nxt = _numeric_next(current)
            if nxt:
                targets.append(nxt)
        if idx > 0:
            targets.append(available[idx - 1])
    else:
        nxt = _numeric_next(current)
        if nxt:
            targets.append(nxt)
        prev = _numeric_prev(current)
        if prev:
            targets.append(prev)
    return targets


def _nyaa_fallback(provider, config, title: str, episode: str) -> List[Server]:
    """The nyaa torrent fallback list for an episode (best-first), or []."""
    if (
        getattr(config.stream, "nyaa_fallback", True)
        and type(provider).__name__ != "Nyaa"
    ):
        from ._source_fallback import nyaa_servers

        return nyaa_servers(
            title, episode, config.stream.translation_type, config.stream.quality
        )
    return []


def resolve_servers(
    provider, config, anime_id: str, title: str, episode: str
) -> List[Server]:
    """Full server list for one episode: primary provider, then nyaa. No cache.

    Safe to call from a background thread - it does no UI/IPC, only network.
    """
    try:
        _t0 = time.perf_counter()
        iterator = provider.episode_streams(
            EpisodeStreamsParams(
                anime_id=anime_id,
                query=title,
                episode=episode,
                translation_type=config.stream.translation_type,
                # Must be passed explicitly: the dataclass default is "720",
                # which silently outranked 1080p torrents on the nyaa-primary
                # path for anyone whose config said 1080.
                quality=config.stream.quality,
            )
        )
        servers = list(iterator) if iterator else []
        logger.info(
            "[ani-timing] resolve_servers ep=%s provider=%s n=%d q=%s took=%.2fs",
            episode,
            type(provider).__name__,
            len(servers),
            config.stream.quality,
            time.perf_counter() - _t0,
        )
    except Exception as e:  # noqa: BLE001 - provider hiccup -> try nyaa
        logger.debug("primary server fetch failed for ep %s: %s", episode, e)
        servers = []

    if not servers:
        servers = _nyaa_fallback(provider, config, title, episode)
    return servers


class PendingServers:
    """Handle to a server resolution whose first result is already available.

    ``first`` is the first extractable server (best-ranked, since providers yield
    best-first) — ready to launch immediately. The remaining servers finish
    resolving in a background thread; ``result()`` blocks until that completes
    and returns the full list (needed later for in-player server switching).
    """

    def __init__(self, first: Optional[Server], servers: Optional[List[Server]] = None):
        self.first = first
        self._servers: List[Server] = (
            list(servers) if servers is not None else ([first] if first else [])
        )
        self._done = threading.Event()

    def result(self, timeout: Optional[float] = None) -> List[Server]:
        """Full server list, blocking until background resolution finishes."""
        self._done.wait(timeout)
        return list(self._servers)


def resolve_first(
    provider, config, anime_id: str, title: str, episode: str
) -> PendingServers:
    """Resolve the FIRST server ASAP; finish the rest in the background.

    Provider-agnostic (relies only on the best-first ``episode_streams``
    contract): consumes the iterator lazily so playback can start on the
    best-ranked source without waiting for the remaining sources to extract.
    The full list finishes resolving in a daemon thread during playback and is
    also cached, so the post-playback server-switch menu has it ready.

    Falls back to the full nyaa list (best-first) when the primary yields
    nothing. A cache hit is returned whole (already resolved, no laziness).
    """
    key = _key(anime_id, episode, config.stream.translation_type)
    cached = _cache_get(key)
    if cached is not None:
        logger.debug("using cached servers for episode %s", episode)
        pending = PendingServers(cached[0] if cached else None, servers=cached)
        pending._done.set()
        return pending

    _t0 = time.perf_counter()
    iterator = None
    try:
        iterator = provider.episode_streams(
            EpisodeStreamsParams(
                anime_id=anime_id,
                query=title,
                episode=episode,
                translation_type=config.stream.translation_type,
                # Explicit: the dataclass default is "720" (see resolve_servers).
                quality=config.stream.quality,
            )
        )
    except Exception as e:  # noqa: BLE001 - provider hiccup -> nyaa
        logger.debug("primary episode_streams failed for ep %s: %s", episode, e)

    first: Optional[Server] = None
    if iterator is not None:
        try:
            first = next(iter(iterator), None)
        except Exception as e:  # noqa: BLE001 - first extract failed -> nyaa
            logger.debug("first extract failed for ep %s: %s", episode, e)
            first = None

    if first is None:
        # Primary yielded nothing extractable -> nyaa fallback (full list).
        servers = _nyaa_fallback(provider, config, title, episode)
        logger.info(
            "[ani-timing] resolve_first ep=%s provider=%s FIRST=nyaa/none q=%s took=%.2fs",
            episode,
            type(provider).__name__,
            config.stream.quality,
            time.perf_counter() - _t0,
        )
        pending = PendingServers(servers[0] if servers else None, servers=servers)
        if servers:
            _cache_put(key, list(servers))
        pending._done.set()
        return pending

    logger.info(
        "[ani-timing] resolve_first ep=%s provider=%s FIRST=%s q=%s took=%.2fs",
        episode,
        type(provider).__name__,
        first.name,
        config.stream.quality,
        time.perf_counter() - _t0,
    )
    pending = PendingServers(first)

    def _drain():
        rest: List[Server] = []
        try:
            rest = list(iterator or [])
        except Exception as e:  # noqa: BLE001 - background drain must not raise
            logger.debug("draining rest failed for ep %s: %s", episode, e)
        finally:
            pending._servers = [first] + rest
            pending._done.set()
            _cache_put(key, list(pending._servers))

    threading.Thread(target=_drain, daemon=True).start()
    return pending


def get_servers(
    provider, config, anime_id: str, title: str, episode: str
) -> List[Server]:
    """Server list for one episode, reusing a cached result if still fresh.

    Caches its own resolve too, so a same-episode re-entry (e.g. Change-Server
    then Replay, which takes this non-TOP path) reuses the list instead of
    re-fetching it.
    """
    key = _key(anime_id, episode, config.stream.translation_type)
    cached = _cache_get(key)
    if cached is not None:
        logger.debug("using cached servers for episode %s", episode)
        return cached
    servers = resolve_servers(provider, config, anime_id, title, episode)
    if servers:
        _cache_put(key, servers)
    return servers


def prefetch_neighbours(provider, config, anime, title: str, current: str) -> None:
    """Kick off background resolution of the current episode's neighbours."""
    for episode in neighbour_episodes(
        anime, config.stream.translation_type, current
    ):
        _prefetch_one(provider, config, anime.id, title, episode)


def _warm_if_torrent(servers) -> None:
    """Hand a just-prefetched torrent episode to the stream session to warm.

    The player's warm helper is a strict no-op unless a torrent stream session
    is already running (i.e. the user is torrent-watching right now), so this
    costs nothing on direct-provider binges.
    """
    try:
        link = servers[0].links[0].link
        if link.startswith("magnet:"):
            from .....libs.player.mpv.player import warm_torrent_stream

            warm_torrent_stream(link)
    except Exception as e:  # noqa: BLE001 - prefetch must never raise
        logger.debug("torrent warm skipped: %s", e)


def _prefetch_one(
    provider, config, anime_id: str, title: str, episode: str
) -> None:
    key = _key(anime_id, episode, config.stream.translation_type)
    if _cache_get(key) is not None:
        return  # already have a fresh list for this episode
    with _LOCK:
        if key in _INFLIGHT:
            return
        _INFLIGHT.add(key)

    def _task():
        try:
            servers = resolve_servers(provider, config, anime_id, title, episode)
            if servers:
                _cache_put(key, servers)
                logger.debug("prefetched %d server(s) for ep %s", len(servers), episode)
                _warm_if_torrent(servers)
        except Exception as e:  # noqa: BLE001 - prefetch must never raise
            logger.debug("prefetch failed for ep %s: %s", episode, e)
        finally:
            with _LOCK:
                _INFLIGHT.discard(key)

    threading.Thread(target=_task, daemon=True).start()


def clear() -> None:
    """Drop all cached/in-flight state (used between sessions and in tests)."""
    with _LOCK:
        _CACHE.clear()
        _INFLIGHT.clear()
