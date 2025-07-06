from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from ..types import (
    AiringSchedule,
    MediaImage,
    MediaItem,
    MediaSearchResult,
    MediaTag,
    MediaTitle,
    MediaTrailer,
    PageInfo,
    Studio,
    UserListStatus,
    UserProfile,
)

if TYPE_CHECKING:
    from .types import AnilistBaseMediaDataSchema, AnilistPageInfo, AnilistUser_

logger = logging.getLogger(__name__)


def _to_generic_media_title(anilist_title: Optional[dict]) -> MediaTitle:
    """Maps an AniList title object to a generic MediaTitle."""
    if not anilist_title:
        return MediaTitle()
    return MediaTitle(
        romaji=anilist_title.get("romaji"),
        english=anilist_title.get("english"),
        native=anilist_title.get("native"),
    )


def _to_generic_media_image(anilist_image: Optional[dict]) -> MediaImage:
    """Maps an AniList image object to a generic MediaImage."""
    if not anilist_image:
        return MediaImage()
    return MediaImage(
        medium=anilist_image.get("medium"),
        large=anilist_image.get("large"),
        extra_large=anilist_image.get("extraLarge"),
    )


def _to_generic_media_trailer(
    anilist_trailer: Optional[dict],
) -> Optional[MediaTrailer]:
    """Maps an AniList trailer object to a generic MediaTrailer."""
    if not anilist_trailer or not anilist_trailer.get("id"):
        return None
    return MediaTrailer(
        id=anilist_trailer["id"],
        site=anilist_trailer.get("site"),
        thumbnail_url=anilist_trailer.get("thumbnail"),
    )


def _to_generic_airing_schedule(
    anilist_schedule: Optional[dict],
) -> Optional[AiringSchedule]:
    """Maps an AniList nextAiringEpisode object to a generic AiringSchedule."""
    if not anilist_schedule or not anilist_schedule.get("airingAt"):
        return None
    return AiringSchedule(
        airing_at=datetime.fromtimestamp(anilist_schedule["airingAt"]),
        episode=anilist_schedule.get("episode", 0),
    )


def _to_generic_studios(anilist_studios: Optional[dict]) -> List[Studio]:
    """Maps AniList studio nodes to a list of generic Studio objects."""
    if not anilist_studios or not anilist_studios.get("nodes"):
        return []
    return [
        Studio(id=s["id"], name=s["name"])
        for s in anilist_studios["nodes"]
        if s.get("id") and s.get("name")
    ]


def _to_generic_tags(anilist_tags: Optional[list[dict]]) -> List[MediaTag]:
    """Maps a list of AniList tags to generic MediaTag objects."""
    if not anilist_tags:
        return []
    return [
        MediaTag(name=t["name"], rank=t.get("rank"))
        for t in anilist_tags
        if t.get("name")
    ]


def _to_generic_user_status(
    anilist_list_entry: Optional[dict],
) -> Optional[UserListStatus]:
    """Maps an AniList mediaListEntry to a generic UserListStatus."""
    if not anilist_list_entry:
        return None

    score = anilist_list_entry.get("score")

    return UserListStatus(
        status=anilist_list_entry.get("status"),
        progress=anilist_list_entry.get("progress"),
        score=score
        if score is not None
        else None,  # AniList score is 0-10, matches our generic model
    )


def _to_generic_media_item(data: AnilistBaseMediaDataSchema) -> MediaItem:
    """Maps a single AniList media schema to a generic MediaItem."""
    return MediaItem(
        id=data["id"],
        id_mal=data.get("idMal"),
        type=data.get("type", "ANIME"),
        title=_to_generic_media_title(data.get("title")),
        status=data.get("status"),
        format=data.get("format"),
        cover_image=_to_generic_media_image(data.get("coverImage")),
        banner_image=data.get("bannerImage"),
        trailer=_to_generic_media_trailer(data.get("trailer")),
        description=data.get("description"),
        episodes=data.get("episodes"),
        duration=data.get("duration"),
        genres=data.get("genres", []),
        tags=_to_generic_tags(data.get("tags")),
        studios=_to_generic_studios(data.get("studios")),
        synonyms=data.get("synonyms", []),
        average_score=data.get("averageScore"),
        popularity=data.get("popularity"),
        favourites=data.get("favourites"),
        next_airing=_to_generic_airing_schedule(data.get("nextAiringEpisode")),
        user_list_status=_to_generic_user_status(data.get("mediaListEntry")),
    )


def _to_generic_page_info(data: AnilistPageInfo) -> PageInfo:
    """Maps an AniList page info object to a generic PageInfo."""
    return PageInfo(
        total=data.get("total", 0),
        current_page=data.get("currentPage", 1),
        has_next_page=data.get("hasNextPage", False),
        per_page=data.get("perPage", 0),
    )


def to_generic_search_result(api_response: dict) -> Optional[MediaSearchResult]:
    """
    Top-level mapper to convert a raw AniList search/list API response
    into a generic MediaSearchResult object.
    """
    if not api_response or "data" not in api_response:
        logger.warning("Mapping failed: API response is missing 'data' key.")
        return None

    page_data = api_response["data"].get("Page")
    if not page_data:
        logger.warning("Mapping failed: API response 'data' is missing 'Page' key.")
        return None

    raw_media_list = page_data.get("media", [])
    media_items: List[MediaItem] = [
        _to_generic_media_item(item) for item in raw_media_list if item
    ]
    page_info = _to_generic_page_info(page_data.get("pageInfo", {}))

    return MediaSearchResult(page_info=page_info, media=media_items)


def to_generic_user_list_result(api_response: dict) -> Optional[MediaSearchResult]:
    """
    Mapper for user list queries where media data is nested inside a 'mediaList' key.
    """
    if not api_response or "data" not in api_response:
        return None
    page_data = api_response["data"].get("Page")
    if not page_data:
        return None

    # Extract media objects from the 'mediaList' array
    media_list_items = page_data.get("mediaList", [])
    raw_media_list = [
        item.get("media") for item in media_list_items if item.get("media")
    ]

    # Now that we have a standard list of media, we can reuse the main search result mapper
    page_data["media"] = raw_media_list
    return to_generic_search_result({"data": {"Page": page_data}})


def to_generic_user_profile(api_response: dict) -> Optional[UserProfile]:
    """Maps a raw AniList viewer response to a generic UserProfile."""
    if not api_response or "data" not in api_response:
        return None

    viewer_data: Optional[AnilistUser_] = api_response["data"].get("Viewer")
    if not viewer_data:
        return None

    return UserProfile(
        id=viewer_data["id"],
        name=viewer_data["name"],
        avatar_url=viewer_data.get("avatar", {}).get("large"),
        banner_url=viewer_data.get("bannerImage"),
    )


def to_generic_relations(api_response: dict) -> Optional[List[MediaItem]]:
    """Maps the 'relations' part of an API response."""
    if not api_response or "data" not in api_response:
        return None
    nodes = (
        api_response.get("data", {})
        .get("Media", {})
        .get("relations", {})
        .get("nodes", [])
    )
    return [_to_generic_media_item(node) for node in nodes if node]


def to_generic_recommendations(api_response: dict) -> Optional[List[MediaItem]]:
    """Maps the 'recommendations' part of an API response."""
    if not api_response or "data" not in api_response:
        return None
    recs = (
        api_response.get("data", {})
        .get("Media", {})
        .get("recommendations", {})
        .get("nodes", [])
    )
    return [
        _to_generic_media_item(rec.get("mediaRecommendation"))
        for rec in recs
        if rec.get("mediaRecommendation")
    ]
