from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Literal, Optional

# --- Generic Enums and Type Aliases ---

MediaType = Literal["ANIME", "MANGA"]
MediaStatus = Literal[
    "FINISHED", "RELEASING", "NOT_YET_RELEASED", "CANCELLED", "HIATUS"
]
UserListStatusType = Literal[
    "CURRENT", "PLANNING", "COMPLETED", "DROPPED", "PAUSED", "REPEATING"
]

# --- Generic Data Models ---


@dataclass(frozen=True)
class MediaImage:
    """A generic representation of media imagery URLs."""

    large: str
    medium: Optional[str] = None
    extra_large: Optional[str] = None


@dataclass(frozen=True)
class MediaTitle:
    """A generic representation of media titles."""

    romaji: Optional[str] = None
    english: Optional[str] = None
    native: Optional[str] = None


@dataclass(frozen=True)
class MediaTrailer:
    """A generic representation of a media trailer."""

    id: str
    site: str  # e.g., "youtube"
    thumbnail_url: Optional[str] = None


@dataclass(frozen=True)
class AiringSchedule:
    """A generic representation of the next airing episode."""

    episode: int
    airing_at: datetime | None = None


@dataclass(frozen=True)
class Studio:
    """A generic representation of an animation studio."""

    id: int | None = None
    name: str | None = None
    favourites: int | None = None
    is_animation_studio: bool | None = None


@dataclass(frozen=True)
class MediaTag:
    """A generic representation of a descriptive tag."""

    name: str
    rank: Optional[int] = None  # Percentage relevance from 0-100


@dataclass(frozen=True)
class UserListStatus:
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


@dataclass(frozen=True)
class MediaItem:
    """
    The definitive, backend-agnostic representation of a single media item.
    This is the primary data model the application will interact with.
    """

    id: int
    id_mal: Optional[int] = None
    type: MediaType = "ANIME"
    title: MediaTitle = field(default_factory=MediaTitle)
    status: Optional[str] = None
    format: Optional[str] = None  # e.g., TV, MOVIE, OVA

    cover_image: Optional[MediaImage] = None
    banner_image: Optional[str] = None
    trailer: Optional[MediaTrailer] = None

    description: Optional[str] = None
    episodes: Optional[int] = None
    duration: Optional[int] = None  # In minutes
    genres: List[str] = field(default_factory=list)
    tags: List[MediaTag] = field(default_factory=list)
    studios: List[Studio] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)

    average_score: Optional[float] = None
    popularity: Optional[int] = None
    favourites: Optional[int] = None

    next_airing: Optional[AiringSchedule] = None

    # user related
    user_status: Optional[UserListStatus] = None


@dataclass(frozen=True)
class PageInfo:
    """Generic pagination information."""

    total: int
    current_page: int
    has_next_page: bool
    per_page: int


@dataclass(frozen=True)
class MediaSearchResult:
    """A generic representation of a page of media search results."""

    page_info: PageInfo
    media: List[MediaItem] = field(default_factory=list)


@dataclass(frozen=True)
class UserProfile:
    """A generic representation of a user's profile."""

    id: int
    name: str
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None
