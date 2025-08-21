from httpx import Response

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


def map_to_search_results(response: Response) -> SearchResults:
    """
    animes = list[Anime]()
       for result in results:
           title, anilist_id, info = self._parse_info(result)
           anime = Anime(title, result['id'])
           anime._set_info(anilist_id, info)
           animes.append(anime)

       return animes
    """
    data = response.json().get("records", [])

    return SearchResults(
        page_info=PageInfo(),
        results=[
            SearchResult(
                id=str(result["id"]),
                title=get_real_title(result),
                episodes=AnimeEpisodes(
                    sub=(
                        list(map(str, range(1, result["episodes_count"] + 1)))
                        if result["dub"] == 0
                        else []
                    ),
                    dub=(
                        list(map(str, range(1, result["episodes_count"] + 1)))
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


def map_to_anime_result(response: Response, search_result: SearchResult) -> Anime:
    data = response.json()["episodes"]
    return Anime(
        id=search_result.id,
        title=search_result.title,
        episodes=search_result.episodes,
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
