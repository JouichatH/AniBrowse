from dataclasses import dataclass
from typing import List, Literal, Optional, Union

from .types import UserListStatusType


@dataclass(frozen=True)
class ApiSearchParams:
    query: Optional[str] = None
    page: int = 1
    per_page: int = 20
    sort: Optional[Union[str, List[str]]] = None

    # IDs
    id_in: Optional[List[int]] = None

    # Genres
    genre_in: Optional[List[str]] = None
    genre_not_in: Optional[List[str]] = None

    # Tags
    tag_in: Optional[List[str]] = None
    tag_not_in: Optional[List[str]] = None

    # Status
    status_in: Optional[List[str]] = None  # Corresponds to [MediaStatus]
    status: Optional[str] = None  # Corresponds to MediaStatus
    status_not_in: Optional[List[str]] = None  # Corresponds to [MediaStatus]

    # Popularity
    popularity_greater: Optional[int] = None
    popularity_lesser: Optional[int] = None

    # Average Score
    averageScore_greater: Optional[int] = None
    averageScore_lesser: Optional[int] = None

    # Season and Year
    seasonYear: Optional[int] = None
    season: Optional[str] = None

    # Start Date (FuzzyDateInt is often an integer representation like YYYYMMDD)
    startDate_greater: Optional[int] = None
    startDate_lesser: Optional[int] = None
    startDate: Optional[int] = None

    # End Date (FuzzyDateInt)
    endDate_greater: Optional[int] = None
    endDate_lesser: Optional[int] = None

    # Format and Type
    format_in: Optional[List[str]] = None  # Corresponds to [MediaFormat]
    type: Optional[str] = None  # Corresponds to MediaType (e.g., "ANIME", "MANGA")

    # On List
    on_list: Optional[bool] = None


@dataclass(frozen=True)
class UserListParams:
    status: UserListStatusType
    page: int = 1
    per_page: int = 20


@dataclass(frozen=True)
class UpdateListEntryParams:
    media_id: int
    status: Optional[UserListStatusType] = None
    progress: Optional[str] = None
    score: Optional[float] = None
