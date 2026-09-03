"""Map Jikan (MyAnimeList) responses onto the app's generic media model.

Jikan is the backend the app falls back to when AniList is unreachable - AniList
disabled its API outright in 2026-08 - so this mapper has to be forgiving: MAL
carries fields AniList does not (and vice versa), and a single unexpected value
must never take down a whole page of results.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..types import (
    MediaFormat,
    MediaGenre,
    MediaImage,
    MediaItem,
    MediaSearchResult,
    MediaStatus,
    MediaTitle,
    PageInfo,
    Studio,
)

logger = logging.getLogger(__name__)

JIKAN_STATUS_MAP = {
    "Finished Airing": MediaStatus.FINISHED,
    "Currently Airing": MediaStatus.RELEASING,
    "Not yet aired": MediaStatus.NOT_YET_RELEASED,
}

# MAL's "type" onto our format enum. MAL has no TV_SHORT/NOVEL/ONE_SHOT.
JIKAN_FORMAT_MAP = {
    "TV": MediaFormat.TV,
    "Movie": MediaFormat.MOVIE,
    "OVA": MediaFormat.OVA,
    "ONA": MediaFormat.ONA,
    "Special": MediaFormat.SPECIAL,
    "Music": MediaFormat.MUSIC,
}

#: Genre names our MediaGenre enum accepts, for filtering MAL's wider list.
_KNOWN_GENRES = {g.value for g in MediaGenre}


def _to_generic_title(jikan_titles: List[dict], fallback: Optional[str]) -> MediaTitle:
    """Extract romaji/english/native from MAL's list of typed titles."""
    romaji = english = native = None
    for t in jikan_titles:
        if not isinstance(t, dict):
            continue
        type_, title_ = t.get("type"), t.get("title")
        if type_ == "Default":
            romaji = title_
        elif type_ == "English":
            english = title_
        elif type_ == "Japanese":
            native = title_

    romaji = romaji or fallback
    return MediaTitle(
        romaji=romaji,
        english=english or romaji or native or "NOT AVAILABLE",
        native=native,
    )


def _synonyms(jikan_titles: List[dict]) -> List[str]:
    """Alternative titles, which the provider search falls back to on a miss.

    A MAL entry's romaji title often differs from what a streaming provider
    calls the show, so these are load-bearing, not decoration.
    """
    out = []
    for t in jikan_titles:
        if not isinstance(t, dict):
            continue
        if t.get("type") in ("Synonym", "Japanese") and t.get("title"):
            out.append(str(t["title"]))
    return list(dict.fromkeys(out))


def _to_generic_image(jikan_images: dict) -> MediaImage:
    if not isinstance(jikan_images, dict):
        return MediaImage(large="")
    jpg = jikan_images.get("jpg") or {}
    webp = jikan_images.get("webp") or {}
    source = jpg if jpg.get("large_image_url") else webp
    return MediaImage(
        large=source.get("large_image_url") or source.get("image_url") or "",
        medium=source.get("image_url"),
    )


def _genres(data: dict) -> List[MediaGenre]:
    """MAL genres that our enum knows about.

    MAL ships genres AniList never had ("Award Winning", "Suspense",
    "Gourmet", "Boys Love", ...). Passing one to the pydantic model raises and
    would kill the entire results page, so unknown names are dropped.
    """
    names = []
    for bucket in ("genres", "themes", "demographics"):
        for g in data.get(bucket) or []:
            if isinstance(g, dict) and g.get("name") in _KNOWN_GENRES:
                names.append(g["name"])
    return [MediaGenre(n) for n in dict.fromkeys(names)]


def _studios(data: dict) -> List[Studio]:
    out = []
    for s in data.get("studios") or []:
        if isinstance(s, dict) and s.get("mal_id") and s.get("name"):
            out.append(Studio(id=s["mal_id"], name=s["name"]))
    return out


def _date(value: Any) -> Optional[datetime]:
    """Parse one of MAL's ISO-8601 aired dates, tolerating nulls and offsets."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _to_generic_media_item(data: dict) -> Optional[MediaItem]:
    """Map one MAL anime entry, or None if it is unusable."""
    mal_id = data.get("mal_id")
    if not mal_id:
        return None

    aired = data.get("aired") or {}
    duration = data.get("duration")
    # MAL gives duration as prose ("24 min per ep"); the model wants minutes.
    minutes = None
    if isinstance(duration, str):
        head = duration.split(" ")[0]
        minutes = int(head) if head.isdigit() else None

    try:
        return MediaItem(
            id=mal_id,
            id_mal=mal_id,
            title=_to_generic_title(data.get("titles") or [], data.get("title")),
            synonymns=_synonyms(data.get("titles") or []),
            cover_image=_to_generic_image(data.get("images") or {}),
            status=JIKAN_STATUS_MAP.get(data.get("status") or "", MediaStatus.UNKNOWN),
            format=JIKAN_FORMAT_MAP.get(data.get("type") or ""),
            episodes=data.get("episodes"),
            duration=minutes,
            average_score=data.get("score"),
            popularity=data.get("members"),
            favourites=data.get("favorites"),
            description=data.get("synopsis"),
            genres=_genres(data),
            studios=_studios(data),
            start_date=_date(aired.get("from")),
            end_date=_date(aired.get("to")),
            # MAL exposes neither per-episode stream metadata nor list status here.
            streaming_episodes={},
            user_status=None,
        )
    except Exception as e:  # noqa: BLE001 - one bad entry must not lose the page
        logger.debug("skipping unmappable Jikan entry %s: %s", mal_id, e)
        return None


def to_generic_search_result(api_response: Dict) -> Optional[MediaSearchResult]:
    """Top-level mapper for a Jikan list response (/anime, /top/anime, /seasons)."""
    if not isinstance(api_response, dict) or "data" not in api_response:
        return None

    raw = api_response.get("data") or []
    if isinstance(raw, dict):  # single-entity endpoints (/anime/{id})
        raw = [raw]

    media = [m for m in (_to_generic_media_item(i) for i in raw if isinstance(i, dict)) if m]

    pagination = api_response.get("pagination") or {}
    items = pagination.get("items") or {}
    return MediaSearchResult(
        page_info=PageInfo(
            total=items.get("total", len(media)),
            current_page=pagination.get("current_page", 1),
            has_next_page=pagination.get("has_next_page", False),
            per_page=items.get("per_page", len(media) or 25),
        ),
        media=media,
    )
