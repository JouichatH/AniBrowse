from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from ..types import (
    AiringSchedule,
    MediaImage,
    MediaItem,
    MediaSearchResult,
    MediaStatus,
    MediaTag,
    MediaTitle,
    PageInfo,
    Studio,
    UserListStatus,
    UserProfile,
)

if TYPE_CHECKING:
    # Jikan doesn't have a formal schema like GraphQL, so we work with dicts.
    pass

# Jikan uses specific strings for status, we can map them to our generic enum.
JIKAN_STATUS_MAP = {
    "Finished Airing": "FINISHED",
    "Currently Airing": "RELEASING",
    "Not yet aired": "NOT_YET_RELEASED",
}


def _to_generic_title(jikan_titles: list[dict]) -> MediaTitle:
    """Extracts titles from Jikan's list of title objects."""
    title_obj = MediaTitle()
    # Jikan's default title is often the romaji one.
    # We prioritize specific types if available.
    for t in jikan_titles:
        type_ = t.get("type")
        title_ = t.get("title")
        if type_ == "Default":
            title_obj.romaji = title_
        elif type_ == "English":
            title_obj.english = title_
        elif type_ == "Japanese":
            title_obj.native = title_
    return title_obj


def _to_generic_image(jikan_images: dict) -> MediaImage:
    """Maps Jikan's image structure."""
    if not jikan_images:
        return MediaImage()
    # Jikan provides different image formats under a 'jpg' key.
    jpg_images = jikan_images.get("jpg", {})
    return MediaImage(
        medium=jpg_images.get("image_url"),
        large=jpg_images.get("large_image_url"),
    )


def _to_generic_media_item(data: dict) -> MediaItem:
    """Maps a single Jikan anime entry to our generic MediaItem."""

    # Jikan score is 0-10, our generic model is 0-10, so we can use it directly.
    # AniList was 0-100, so its mapper had to divide by 10.
    score = data.get("score")

    return MediaItem(
        id=data["mal_id"],
        id_mal=data["mal_id"],
        title=_to_generic_title(data.get("titles", [])),
        cover_image=_to_generic_image(data.get("images", {})),
        status=JIKAN_STATUS_MAP.get(data.get("status")),
        episodes=data.get("episodes"),
        duration=data.get("duration"),
        average_score=score,
        popularity=data.get("popularity"),
        favourites=data.get("favorites"),
        description=data.get("synopsis"),
        genres=[g["name"] for g in data.get("genres", [])],
        studios=[
            Studio(id=s["mal_id"], name=s["name"]) for s in data.get("studios", [])
        ],
        # Jikan doesn't provide user list status in its search results.
        user_list_status=None,
    )


def to_generic_search_result(api_response: dict) -> Optional[MediaSearchResult]:
    """Top-level mapper for Jikan search results."""
    if not api_response or "data" not in api_response:
        return None

    media_items = [_to_generic_media_item(item) for item in api_response["data"]]

    pagination = api_response.get("pagination", {})
    page_info = PageInfo(
        total=pagination.get("items", {}).get("total", 0),
        current_page=pagination.get("current_page", 1),
        has_next_page=pagination.get("has_next_page", False),
        per_page=pagination.get("items", {}).get("per_page", 25),
    )

    return MediaSearchResult(page_info=page_info, media=media_items)
