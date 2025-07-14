from typing import Literal

from pydantic import BaseModel


class BaseAnimeProviderModel(BaseModel):
    pass


class PageInfo(BaseAnimeProviderModel):
    total: int | None = None
    per_page: int | None = None
    current_page: int | None = None


class AnimeEpisodes(BaseAnimeProviderModel):
    sub: list[str]
    dub: list[str] = []
    raw: list[str] = []


class SearchResult(BaseAnimeProviderModel):
    id: str
    title: str
    episodes: AnimeEpisodes
    other_titles: list[str] = []
    media_type: str | None = None
    score: int | None = None
    status: str | None = None
    season: str | None = None
    poster: str | None = None


class SearchResults(BaseAnimeProviderModel):
    page_info: PageInfo
    results: list[SearchResult]


class AnimeEpisodeInfo(BaseAnimeProviderModel):
    id: str
    episode: str
    title: str | None = None
    poster: str | None = None
    duration: str | None = None


class Anime(BaseAnimeProviderModel):
    id: str
    title: str
    episodes: AnimeEpisodes
    type: str | None = None
    episodes_info: list[AnimeEpisodeInfo] | None = None
    poster: str | None = None
    year: str | None = None


class EpisodeStream(BaseAnimeProviderModel):
    # episode: str
    link: str
    title: str | None = None
    quality: Literal["360", "480", "720", "1080"] = "720"
    translation_type: Literal["dub", "sub"] = "sub"
    format: str | None = None
    hls: bool | None = None
    mp4: bool | None = None
    priority: int | None = None


class Subtitle(BaseAnimeProviderModel):
    url: str
    language: str | None = None


class Server(BaseAnimeProviderModel):
    name: str
    links: list[EpisodeStream]
    episode_title: str | None = None
    headers: dict[str, str] = dict()
    subtitles: list[Subtitle] = []
    audio: list[str] = []
