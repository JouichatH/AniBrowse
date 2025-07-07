import logging
import random
import time
from typing import TYPE_CHECKING

from yt_dlp.utils import (
    extract_attributes,
    get_element_by_id,
    get_elements_html_by_class,
)

from ..base import BaseAnimeProvider
from ..params import AnimeParams, EpisodeStreamsParams, SearchParams
from ..types import Anime, SearchResults, Server
from ..utils.debug import debug_provider
from .constants import (
    ANIMEPAHE_BASE,
    ANIMEPAHE_ENDPOINT,
    JUICY_STREAM_REGEX,
    REQUEST_HEADERS,
    SERVER_HEADERS,
)
from .extractors import process_animepahe_embed_page
from .parser import map_to_anime_result, map_to_server, map_to_search_results
from .types import AnimePaheAnimePage, AnimePaheSearchPage, AnimePaheSearchResult

logger = logging.getLogger(__name__)


class AnimePahe(BaseAnimeProvider):
    HEADERS = REQUEST_HEADERS

    @debug_provider
    def search(self, params: SearchParams) -> SearchResults | None:
        response = self.client.get(
            ANIMEPAHE_ENDPOINT, params={"m": "search", "q": params.query}
        )
        response.raise_for_status()
        data: AnimePaheSearchPage = response.json()
        return map_to_search_results(data)

    @debug_provider
    def get(self, params: AnimeParams) -> Anime | None:
        page = 1
        standardized_episode_number = 0
        anime_result: AnimePaheSearchResult = self.search(SearchParams(query=params.id)).results[0]
        data: AnimePaheAnimePage = {}  # pyright:ignore

        def _pages_loader(
        self,
        data,
        session_id,
        params,
        page,
        standardized_episode_number,
    ):
        response = self.client.get(ANIMEPAHE_ENDPOINT, params=params)
        response.raise_for_status()
        if not data:
            data.update(response.json())
        elif ep_data := response.json().get("data"):
            data["data"].extend(ep_data)
        if response.json()["next_page_url"]:
            # TODO: Refine this
            time.sleep(
                random.choice(
                    [
                        0.25,
                        0.1,
                        0.5,
                        0.75,
                        1,
                    ]
                )
            )
            page += 1
            self._pages_loader(
                data,
                session_id,
                params={
                    "m": "release",
                    "page": page,
                    "id": session_id,
                    "sort": "episode_asc",
                },
                page=page,
                standardized_episode_number=standardized_episode_number,
            )
        else:
            for episode in data.get("data", []):
                if episode["episode"] % 1 == 0:
                    standardized_episode_number += 1
                    episode.update({"episode": standardized_episode_number})
                else:
                    standardized_episode_number += episode["episode"] % 1
                    episode.update({"episode": standardized_episode_number})
                    standardized_episode_number = int(standardized_episode_number)
        return data

    @debug_provider
    def get(self, params: AnimeParams) -> Anime | None:
        page = 1
        standardized_episode_number = 0
        search_results = self.search(SearchParams(query=params.id))
        if not search_results or not search_results.results:
            logger.error(f"[ANIMEPAHE-ERROR]: No search results found for ID {params.id}")
            return None
        anime_result: AnimePaheSearchResult = search_results.results[0]

        data: AnimePaheAnimePage = {}  # pyright:ignore

        data = self._pages_loader(
            data,
            params.id,
            params={
                "m": "release",
                "id": params.id,
                "sort": "episode_asc",
                "page": page,
            },
            page=page,
            standardized_episode_number=standardized_episode_number,
        )

        if not data:
            return None
        
        # Construct AnimePaheAnime TypedDict for mapping
        anime_pahe_anime_data = {
            "id": params.id,
            "title": anime_result.title,
            "year": anime_result.year,
            "season": anime_result.season,
            "poster": anime_result.poster,
            "score": anime_result.score,
            "availableEpisodesDetail": {
                "sub": list(map(str, [episode["episode"] for episode in data["data"]])),
                "dub": list(map(str, [episode["episode"] for episode in data["data"]])),
                "raw": list(map(str, [episode["episode"] for episode in data["data"]])),
            },
            "episodesInfo": [
                {
                    "title": episode["title"],
                    "episode": episode["episode"],
                    "id": episode["session"],
                    "translation_type": episode["audio"],
                    "duration": episode["duration"],
                    "poster": episode["snapshot"],
                }
                for episode in data["data"]
            ],
        }
        return map_to_anime_result(anime_pahe_anime_data)

    @debug_provider
    def episode_streams(self, params: EpisodeStreamsParams) -> "Iterator[Server] | None":
        anime_info = self.get(AnimeParams(id=params.anime_id))
        if not anime_info:
            logger.error(
                f"[ANIMEPAHE-ERROR]: Anime with ID {params.anime_id} not found"
            )
            return

        episode = next(
            (
                ep
                for ep in anime_info.episodes_info
                if float(ep.episode) == float(params.episode)
            ),
            None,
        )

        if not episode:
            logger.error(
                f"[ANIMEPAHE-ERROR]: Episode {params.episode} doesn't exist for anime {anime_info.title}"
            )
            return

        url = f"{ANIMEPAHE_BASE}/play/{params.anime_id}/{episode.id}"
        response = self.client.get(url)
        response.raise_for_status()

        c = get_element_by_id("resolutionMenu", response.text)
        resolutionMenuItems = get_elements_html_by_class("dropdown-item", c)
        res_dicts = [extract_attributes(item) for item in resolutionMenuItems]

        streams = {
            "server": "kwik",
            "links": [],
            "episode_title": f"{episode.title or anime_info.title}; Episode {episode.episode}",
            "subtitles": [],
            "headers": {},
        }

        for res_dict in res_dicts:
            embed_url = res_dict["data-src"]
            data_audio = "dub" if res_dict["data-audio"] == "eng" else "sub"

            if data_audio != params.translation_type:
                continue

            if not embed_url:
                logger.warning(
                    "[ANIMEPAHE-WARN]: embed url not found please report to the developers"
                )
                continue

            embed_response = self.client.get(
                embed_url, headers={"User-Agent": self.client.headers["User-Agent"], **SERVER_HEADERS}
            )
            embed_response.raise_for_status()
            embed_page = embed_response.text

            decoded_js = process_animepahe_embed_page(embed_page)
            if not decoded_js:
                logger.error("[ANIMEPAHE-ERROR]: failed to decode embed page")
                continue
            juicy_stream = JUICY_STREAM_REGEX.search(decoded_js)
            if not juicy_stream:
                logger.error("[ANIMEPAHE-ERROR]: failed to find juicy stream")
                continue
            juicy_stream = juicy_stream.group(1)

            streams["links"].append(
                {
                    "quality": res_dict["data-resolution"],
                    "translation_type": data_audio,
                    "link": juicy_stream,
                }
            )
        if streams["links"]:
            yield map_to_server(streams)


if __name__ == "__main__":
    from httpx import Client
    from ..utils.debug import test_anime_provider

    test_anime_provider(AnimePahe, Client())
