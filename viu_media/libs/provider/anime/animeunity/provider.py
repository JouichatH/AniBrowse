import logging
import re
import time
from functools import lru_cache

import httpx

from ...scraping.user_agents import UserAgentGenerator
from ..base import BaseAnimeProvider
from ..params import AnimeParams, EpisodeStreamsParams, SearchParams
from ..types import Anime, AnimeEpisodeInfo, SearchResult, SearchResults
from ..utils.debug import debug_provider
from .constants import ANIMEUNITY_BASE, DOWNLOAD_URL_REGEX, MAX_TIMEOUT
from .mappers import map_to_anime_result, map_to_search_results, map_to_server

logger = logging.getLogger(__name__)


class AnimeUnity(BaseAnimeProvider):
    HEADERS = {
        "user-agent": UserAgentGenerator().random(),
    }

    @lru_cache
    def _get_token(self) -> dict[str, str]:
        response = self.client.get(ANIMEUNITY_BASE, headers=self.HEADERS)
        data = response.cookies
        cookies = {
            "animeunity_session": data["animeunity_session"],
        }

        self.HEADERS["x-xsrf-token"] = data["XSRF-TOKEN"]
        return cookies

    @debug_provider
    def search(self, params: SearchParams) -> SearchResults | None:
        return self._search(params)

    @lru_cache
    def _search(self, params: SearchParams) -> SearchResults | None:
        cookies = self._get_token()
        try:
            response = self.client.post(
                url=f"{ANIMEUNITY_BASE}/livesearch",
                data={"title": params.query},
                headers=self.HEADERS,
                cookies=cookies,
                timeout=MAX_TIMEOUT,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"AnimeUnity 500 error for query '{params.query}'")
            # Opzionale: retry dopo un breve delay
            logger.info("Retrying after 2 seconds...")
            time.sleep(2)
            return self._search(params)
        return map_to_search_results(response)

    @debug_provider
    def get(self, params: AnimeParams) -> Anime | None:
        return self._get_anime(params)

    @lru_cache()
    def _get_search_result(self, params: AnimeParams) -> SearchResult | None:
        search_results = self._search(SearchParams(query=params.query))
        if not search_results or not search_results.results:
            logger.error(f"No search results found for ID {params.id}")
            return None
        for search_result in search_results.results:
            if search_result.id == params.id:
                return search_result

    @lru_cache
    def _get_anime(self, params: AnimeParams) -> Anime | None:
        search_result = self._get_search_result(params)
        if not search_result:
            logger.error(f"No search result found for ID {params.id}")
            return None

        cookies = self._get_token()
        response = self.client.get(
            url=f"{ANIMEUNITY_BASE}/info_api/{params.id}/1",
            params={
                "start_range": 0,
                "end_range": max(
                    len(search_result.episodes.sub), len(search_result.episodes.dub)
                ),
            },
            headers=self.HEADERS,
            cookies=cookies,
            timeout=MAX_TIMEOUT,
        )
        response.raise_for_status()
        return map_to_anime_result(response, search_result)

    @lru_cache()
    def _get_episode_info(
        self, params: EpisodeStreamsParams
    ) -> AnimeEpisodeInfo | None:
        anime_info = self._get_anime(
            AnimeParams(id=params.anime_id, query=params.query)
        )
        if not anime_info:
            logger.error(f"No anime info for {params.anime_id}")
            return
        if not anime_info.episodes_info:
            logger.error(f"No episodes info for {params.anime_id}")
            return
        for episode in anime_info.episodes_info:
            if episode.episode == params.episode:
                return episode

    @debug_provider
    def episode_streams(self, params):
        episode = self._get_episode_info(params)
        if not episode:
            logger.error(
                f"Episode {params.episode} doesn't exist for anime {params.anime_id}"
            )
            return

        cookies = self._get_token()
        response = self.client.get(
            url=f"{ANIMEUNITY_BASE}/embed-url/{episode.id}",
            headers=self.HEADERS,
            cookies=cookies,
            timeout=MAX_TIMEOUT,
        )
        response.raise_for_status()
        # The embed URL is returned as plain text
        iframe_src = response.text.strip()
        # Fetch the video page
        video_response = self.client.get(
            iframe_src, headers=self.HEADERS, cookies=cookies, timeout=MAX_TIMEOUT
        )
        video_response.raise_for_status()

        download_url_match = re.search(DOWNLOAD_URL_REGEX, video_response.text)
        if download_url_match:
            yield map_to_server(episode, download_url_match.group(1))
        return None


if __name__ == "__main__":
    from ..utils.debug import test_anime_provider

    test_anime_provider(AnimeUnity)
