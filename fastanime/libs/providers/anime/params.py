from dataclasses import dataclass
from typing import Literal


@dataclass
class SearchParams:
    """Parameters for searching anime."""

    query: str

    # pagination and sorting
    current_page: int = 1
    page_limit: int = 20
    sort_by: str = "relevance"
    order: Literal["asc", "desc"] = "desc"

    # filters
    translation_type: Literal["sub", "dub"] = "sub"
    genre: str | None = None
    year: int | None = None
    status: str | None = None
    allow_nsfw: bool = True
    allow_unknown: bool = True
    country_of_origin: str | None = None


@dataclass
class EpisodeStreamsParams:
    """Parameters for fetching episode streams."""

    anime_id: str
    episode: str
    translation_type: Literal["sub", "dub"] = "sub"
    server: str | None = None
    quality: Literal["1080", "720", "480", "360"] = "720"
    subtitles: bool = True


@dataclass
class AnimeParams:
    """Parameters for fetching anime details."""

    id: str
