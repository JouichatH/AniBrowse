from ..types import (
    Anime,
    AnimeEpisodeInfo,
    AnimeEpisodes,
    EpisodeStream,
    MediaTranslationType,
    PageInfo,
    SearchResult,
    SearchResults,
    Server,
)

translation_type_map = {
    "sub": MediaTranslationType.SUB,
    "dub": MediaTranslationType.DUB,
    "raw": MediaTranslationType.RAW,
}


def map_to_search_results(data: dict) -> SearchResults:
    return SearchResults(
        page_info=PageInfo(),
        results=[
            SearchResult(
                id=str(result["id"]),
                title=get_real_title(result),
                episodes=AnimeEpisodes(
                    sub=(
                        list(map(str, range(1, get_episodes_count(result) + 1)))
                        if result["dub"] == 0
                        else []
                    ),
                    dub=(
                        list(map(str, range(1, get_episodes_count(result) + 1)))
                        if result["dub"] == 1
                        else []
                    ),
                ),
                # other_titles=[title for title in [result["title_eng"], result["title_it"]] if title],
                media_type=result["type"],
                score=result["score"],
                status=result["status"],
                season=result["season"],
                poster=result["imageurl"],
                year=result["date"],
            )
            for result in data
        ],
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
                # session_id=episode.get("session_id"),
                title=f"{search_result.title} - Ep {episode['number']}",
                # poster=episode["tg_post"],
                # duration=episode.get("duration"),
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
                # translation_type=translation_type_map[episode.]
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
    if record.get("episodes_count", 0) > 0:
        return record["episodes_count"]
    else:
        return record.get("real_episodes_count", 0)
