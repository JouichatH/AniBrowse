"""nyaa torrent fallback for a lagging or failing primary source.

When the active streaming provider (e.g. AllAnime) trails the broadcast for a
simulcast, an episode can be aired yet absent from that source. These helpers
let the interactive menus surface and stream those episodes from nyaa torrents,
which carry the fastest English releases and dodge the anti-bot walls.

Everything is best-effort and swallows errors: a nyaa hiccup must never break
the normal flow, it just means no fallback is offered.
"""

from __future__ import annotations

import logging
from typing import List

from .....libs.provider.anime.params import EpisodeStreamsParams, SearchParams
from .....libs.provider.anime.provider import ProviderName, create_provider
from .....libs.provider.anime.types import Server

logger = logging.getLogger(__name__)


def _as_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _nyaa():
    return create_provider(ProviderName.NYAA)


def nyaa_servers(
    title: str,
    episode: str,
    translation_type: str = "sub",
    quality: str = "1080",
) -> List[Server]:
    """Streamable nyaa servers (magnets) for one episode, or [] if none."""
    try:
        iterator = _nyaa().episode_streams(
            EpisodeStreamsParams(
                query=title,
                anime_id=title,  # nyaa keys off the title, not a provider id
                episode=str(episode),
                translation_type=translation_type,  # type: ignore[arg-type]
                quality=quality,  # type: ignore[arg-type]
            )
        )
        return list(iterator) if iterator else []
    except Exception as e:  # noqa: BLE001 - fallback must never raise
        logger.debug("nyaa stream fallback failed for %r ep %s: %s", title, episode, e)
        return []


def nyaa_extra_episodes(
    title: str, existing: List[str], last_aired: int
) -> List[str]:
    """Episode numbers nyaa has that the primary source lacks (up to last_aired)."""
    try:
        results = _nyaa().search(SearchParams(query=title))
    except Exception as e:  # noqa: BLE001
        logger.debug("nyaa episode lookup failed for %r: %s", title, e)
        return []
    if not results or not results.results:
        return []
    have = {str(e) for e in existing}
    return [
        e
        for e in results.results[0].episodes.sub
        if e not in have and _as_float(e) <= last_aired
    ]


def merge_episodes(base: List[str], extra: List[str]) -> List[str]:
    """Union of two episode-number lists, sorted numerically."""
    seen = {str(e) for e in base}
    return sorted(
        list(base) + [e for e in extra if e not in seen], key=_as_float
    )
