from dataclasses import dataclass
from typing import Literal


@dataclass
class PageInfo:
    total: int | None = None
    per_page: int | None = None
    current_page: int | None = None


@dataclass
class AnimeEpisodes:
    sub: list[str]
    dub: list[str] = []
    raw: list[str] = []


@dataclass
class SearchResult:
    id: str
    title: str
    available_episodes: AnimeEpisodes
    other_titles: list[str] = []
    media_type: str | None = None
    score: int | None = None
    status: str | None = None
    season: str | None = None
    poster: str | None = None


@dataclass
class SearchResults:
    page_info: PageInfo
    results: list[SearchResult]


@dataclass
class AnimeEpisodeInfo:
    id: str
    title: str
    episode: str
    poster: str | None
    duration: str | None
    translation_type: str | None


@dataclass
class Anime:
    id: str
    title: str
    episodes: AnimeEpisodes
    type: str | None = None
    episodes_info: list[AnimeEpisodeInfo] | None = None
    poster: str | None = None
    year: str | None = None


@dataclass
class EpisodeStream:
    link: str
    quality: Literal["360", "480", "720", "1080"] = "720"
    translation_type: Literal["dub", "sub"] = "sub"
    resolution: str | None = None
    hls: bool | None = None
    mp4: bool | None = None
    priority: int | None = None


@dataclass
class Subtitle:
    url: str
    language: str | None = None


@dataclass
class Server:
    name: str
    links: list[EpisodeStream]
    episode_title: str | None = None
    headers: dict | None = None
    subtitles: list[Subtitle] | None = None
    audio: list["str"] | None = None
