from typing import Literal

from ..types import (
    Anime,
    AnimeEpisodeInfo,
    AnimeEpisodes,
    EpisodeStream,
    PageInfo,
    SearchResult,
    SearchResults,
    Server,
)


def map_to_search_results(
    data: dict, translation_type: Literal["sub", "dub"]
) -> SearchResults:
    results = []
    for result in data:
        mapped_result = map_to_search_result(result, translation_type)
        if mapped_result:
            results.append(mapped_result)

    return SearchResults(
        page_info=PageInfo(),
        results=results,
    )


def map_to_search_result(
    data: dict, translation_type: Literal["sub", "dub"] | None
) -> SearchResult | None:
    if translation_type and data["dub"] != 1 if translation_type == "dub" else 0:
        return None
    return SearchResult(
        id=str(data["id"]),
        title=get_real_title(data),
        episodes=AnimeEpisodes(
            sub=(
                list(map(str, range(1, get_episodes_count(data) + 1)))
                if data["dub"] == 0
                else []
            ),
            dub=(
                list(map(str, range(1, get_episodes_count(data) + 1)))
                if data["dub"] == 1
                else []
            ),
        ),
        # other_titles=[title for title in [result["title_eng"], result["title_it"]] if title],
        media_type=data["type"],
        score=data["score"],
        status=data["status"],
        # season=result["season"],
        poster=data["imageurl"],
        year=data["date"],
    )


def map_to_anime_result(data: list, search_result: SearchResult) -> Anime:
    return Anime(
        id=search_result.id,
        title=search_result.title,
        episodes=AnimeEpisodes(
            sub=[
                episode["number"]
                for episode in data
                if len(search_result.episodes.sub) > 0
            ],
            dub=[
                episode["number"]
                for episode in data
                if len(search_result.episodes.dub) > 0
            ],
        ),
        episodes_info=[
            AnimeEpisodeInfo(
                id=str(episode["id"]),
                episode=episode["number"],
                title=f"{search_result.title} - Ep {episode['number']}",
            )
            for episode in data
        ],
        type=search_result.media_type,
        poster=search_result.poster,
        year=search_result.year,
    )


def map_to_server(episode: AnimeEpisodeInfo, download_url: str) -> Server:
    return Server(
        name="vixcloud",
        links=[
            EpisodeStream(
                link=download_url,
            )
        ],
        episode_title=episode.title,
    )


def get_real_title(record: dict) -> str:
    """
    Return the most appropriate title from the record.
    """
    if record.get("title_eng"):
        return record["title_eng"]
    elif record.get("title"):
        return record["title"]
    else:
        return record.get("title_it", "")


def get_episodes_count(record: dict) -> int:
    """
    Return the number of episodes from the record.
    """
    if (count := record.get("real_episodes_count", 0)) > 0:
        return count
    return record.get("episodes_count", 0)
