"""AniSkip client: fetch opening/ending skip intervals for an episode.

Skip timestamps come from the community AniSkip API (https://api.aniskip.com),
keyed by MyAnimeList id + episode number. This is the only reliable source of
opening/ending intervals; without it there is nothing to skip.

Everything here is best-effort and swallows errors: a network hiccup or a missing
entry must never break playback, it just means no skip is offered for that episode.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Literal, Optional

logger = logging.getLogger(__name__)

ANISKIP_URL = "https://api.aniskip.com/v2/skip-times"

# AniSkip returns several skip kinds; collapse each to the segment it belongs to.
_OP_KINDS = {"op", "mixed-op"}
_ED_KINDS = {"ed", "mixed-ed"}


@dataclass(frozen=True)
class SkipInterval:
    """One skippable segment of an episode, in seconds."""

    kind: Literal["op", "ed"]
    start: float
    end: float

    def contains(self, t: float) -> bool:
        # Half-open so the seek target (== end) is not itself treated as inside.
        return self.start <= t < self.end


def fetch_skip_times(
    mal_id: Optional[int],
    episode: str | int,
    episode_length: float = 0.0,
    timeout: float = 8.0,
) -> List[SkipInterval]:
    """Opening/ending intervals for one episode, or [] if none/unavailable.

    ``episode_length`` is the real episode duration in seconds when known; AniSkip
    uses it to validate its stored intervals. 0 means "unknown" (no validation).
    """
    if not mal_id:
        return []
    try:
        episode_number = int(float(episode))
    except (TypeError, ValueError):
        logger.debug("aniskip: non-numeric episode %r, skipping lookup", episode)
        return []
    if episode_number <= 0:
        return []

    try:
        import httpx

        url = f"{ANISKIP_URL}/{mal_id}/{episode_number}"
        params = [
            ("types", "op"),
            ("types", "ed"),
            ("episodeLength", str(episode_length or 0)),
        ]
        r = httpx.get(url, params=params, timeout=timeout)
        if r.status_code == 404:
            return []
        r.raise_for_status()
        payload = r.json()
    except Exception as e:  # noqa: BLE001 - skip lookup must never raise
        logger.debug("aniskip lookup failed for mal=%s ep=%s: %s", mal_id, episode, e)
        return []

    if not payload or not payload.get("found"):
        return []

    intervals: List[SkipInterval] = []
    for result in payload.get("results", []) or []:
        skip_type = str(result.get("skipType", "")).lower()
        if skip_type in _OP_KINDS:
            kind: Literal["op", "ed"] = "op"
        elif skip_type in _ED_KINDS:
            kind = "ed"
        else:
            continue  # recap / unknown - not an opening or ending
        interval = result.get("interval") or {}
        try:
            start = float(interval["startTime"])
            end = float(interval["endTime"])
        except (KeyError, TypeError, ValueError):
            continue
        if end > start:
            intervals.append(SkipInterval(kind=kind, start=start, end=end))

    return intervals
