from typing import TYPE_CHECKING

from ..types import Anime, AnimeEpisodes, AnimeEpisodeInfo, PageInfo, SearchResult, SearchResults, Server, EpisodeStream, Subtitle
from .types import AnimePaheAnimePage, AnimePaheSearchResult, AnimePaheSearchPage, AnimePaheServer, AnimePaheEpisodeInfo, AnimePaheAnime, AnimePaheStreamLink


def map_to_search_results(data: AnimePaheSearchPage) -> SearchResults:
    results = []
    for result in data["data"]:
        results.append(
            SearchResult(
                id=result["session"],
                title=result["title"],
                episodes=AnimeEpisodes(
                    sub=list(map(str, range(1, result["episodes"] + 1))),
                    dub=list(map(str, range(1, result["episodes"] + 1))),
                    raw=list(map(str, range(1, result["episodes"] + 1))),
                ),
                media_type=result["type"],
                score=result["score"],
                status=result["status"],
                season=result["season"],
                poster=result["poster"],
            )
        )

    return SearchResults(
        page_info=PageInfo(
            total=data["total"],
            per_page=data["per_page"],
            current_page=data["current_page"],
        ),
        results=results,
    )


def map_to_anime_result(data: AnimePaheAnime) -> Anime:
    episodes_info = []
    for ep_info in data["episodesInfo"]:
        episodes_info.append(
            AnimeEpisodeInfo(
                id=ep_info["id"],
                episode=str(ep_info["episode"]),
                title=ep_info["title"],
                poster=ep_info["poster"],
                duration=ep_info["duration"],
            )
        )

    return Anime(
        id=data["id"],
        title=data["title"],
        episodes=AnimeEpisodes(
            sub=data["availableEpisodesDetail"]["sub"],
            dub=data["availableEpisodesDetail"]["dub"],
            raw=data["availableEpisodesDetail"]["raw"],
        ),
        year=str(data["year"]),
        poster=data["poster"],
        episodes_info=episodes_info,
    )


def map_to_server(data: AnimePaheServer) -> Server:
    links = []
    for link in data["links"]:
        links.append(
            EpisodeStream(
                link=link["link"],
                quality=link["quality"],
                translation_type=link["translation_type"],
            )
        )
    return Server(
        name=data["server"],
        links=links,
        episode_title=data["episode_title"],
        subtitles=data["subtitles"],
        headers=data["headers"],
    )
