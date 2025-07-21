from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# --- Generic Enums and Type Aliases ---

MediaType = Literal["ANIME", "MANGA"]
MediaStatus = Literal[
    "FINISHED", "RELEASING", "NOT_YET_RELEASED", "CANCELLED", "HIATUS"
]
UserListStatusType = Literal[
    "CURRENT", "PLANNING", "COMPLETED", "DROPPED", "PAUSED", "REPEATING"
]

# --- Generic Data Models ---


class BaseApiModel(BaseModel):
    """Base model for all API types."""

    pass


class MediaImage(BaseApiModel):
    """A generic representation of media imagery URLs."""

    large: str
    medium: Optional[str] = None
    extra_large: Optional[str] = None


class MediaTitle(BaseApiModel):
    """A generic representation of media titles."""

    english: str
    romaji: Optional[str] = None
    native: Optional[str] = None


class MediaTrailer(BaseApiModel):
    """A generic representation of a media trailer."""

    id: str
    site: str  # e.g., "youtube"
    thumbnail_url: Optional[str] = None


class AiringSchedule(BaseApiModel):
    """A generic representation of the next airing episode."""

    episode: int
    airing_at: datetime | None = None


class Studio(BaseApiModel):
    """A generic representation of an animation studio."""

    id: int | None = None
    name: str | None = None
    favourites: int | None = None
    is_animation_studio: bool | None = None


class MediaTag(BaseApiModel):
    """A generic representation of a descriptive tag."""

    name: str
    rank: Optional[int] = None  # Percentage relevance from 0-100


class StreamingEpisode(BaseApiModel):
    """A generic representation of a streaming episode."""

    title: str
    thumbnail: Optional[str] = None


class UserListStatus(BaseApiModel):
    """Generic representation of a user's list status for a media item."""

    id: int | None = None

    status: Optional[str] = None
    progress: Optional[int] = None
    score: Optional[float] = None
    repeat: Optional[int] = None
    notes: Optional[str] = None
    start_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[str] = None


class MediaItem(BaseApiModel):
    id: int
    title: MediaTitle
    id_mal: Optional[int] = None
    type: MediaType = "ANIME"
    status: Optional[str] = None
    format: Optional[str] = None  # e.g., TV, MOVIE, OVA

    cover_image: Optional[MediaImage] = None
    banner_image: Optional[str] = None
    trailer: Optional[MediaTrailer] = None

    description: Optional[str] = None
    episodes: Optional[int] = None
    duration: Optional[int] = None  # In minutes
    genres: List[str] = Field(default_factory=list)
    tags: List[MediaTag] = Field(default_factory=list)
    studios: List[Studio] = Field(default_factory=list)
    synonyms: List[str] = Field(default_factory=list)

    average_score: Optional[float] = None
    popularity: Optional[int] = None
    favourites: Optional[int] = None

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    next_airing: Optional[AiringSchedule] = None

    # streaming episodes
    streaming_episodes: List[StreamingEpisode] = Field(default_factory=list)

    # user related
    user_status: Optional[UserListStatus] = None


class PageInfo(BaseApiModel):
    """Generic pagination information."""

    total: int
    current_page: int
    has_next_page: bool
    per_page: int


class MediaSearchResult(BaseApiModel):
    """A generic representation of a page of media search results."""

    page_info: PageInfo
    media: List[MediaItem] = Field(default_factory=list)


class UserProfile(BaseApiModel):
    """A generic representation of a user's profile."""

    id: int
    name: str
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None
