import logging
from functools import lru_cache

from ...scraping.user_agents import UserAgentGenerator
from ..base import BaseAnimeProvider
from ..params import AnimeParams, EpisodeStreamsParams, SearchParams
from ..types import Anime, AnimeEpisodeInfo, SearchResult, SearchResults
from ..utils.debug import debug_provider
from .constants import ANIMEUNITY_BASE, DOWNLOAD_URL_REGEX, MAX_TIMEOUT, TOKEN_REGEX
from .mappers import map_to_anime_result, map_to_search_results, map_to_server

logger = logging.getLogger(__name__)


class AnimeUnity(BaseAnimeProvider):
    HEADERS = {
        "User-Agent": UserAgentGenerator().random(),
    }

    @lru_cache
    def _get_token(self) -> None:
        response = self.client.get(
            ANIMEUNITY_BASE,
            headers=self.HEADERS,
            timeout=MAX_TIMEOUT,
            follow_redirects=True,
        )
        response.raise_for_status()
        token_match = TOKEN_REGEX.search(response.text)
        if token_match:
            self.HEADERS["x-csrf-token"] = token_match.group(1)
        self.client.cookies = {
            "animeunity_session": response.cookies.get("animeunity_session") or ""
        }
        self.client.headers = self.HEADERS

    @debug_provider
    def search(self, params: SearchParams) -> SearchResults | None:
        return self._search(params)

    @lru_cache
    def _search(self, params: SearchParams) -> SearchResults | None:
        self._get_token()
        response = self.client.post(
            url=f"{ANIMEUNITY_BASE}/livesearch",
            data={"title": params.query},
            timeout=MAX_TIMEOUT,
        )
        response.raise_for_status()
        return map_to_search_results(response.json().get("records", []))

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

        # Fetch episodes in chunks
        data = []
        start_range = 1
        episode_count = max(
            len(search_result.episodes.sub), len(search_result.episodes.dub)
        )
        while start_range <= episode_count:
            end_range = min(start_range + 119, episode_count)
            response = self.client.get(
                url=f"{ANIMEUNITY_BASE}/info_api/{params.id}/1",
                params={
                    "start_range": start_range,
                    "end_range": end_range,
                },
                timeout=MAX_TIMEOUT,
            )
            response.raise_for_status()
            data.extend(response.json().get("episodes", []))
            start_range = end_range + 1

        return map_to_anime_result(data, search_result)

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

        response = self.client.get(
            url=f"{ANIMEUNITY_BASE}/embed-url/{episode.id}",
            timeout=MAX_TIMEOUT,
        )
        response.raise_for_status()
        # The embed URL is returned as plain text
        iframe_src = response.text.strip()
        # Fetch the video page
        video_response = self.client.get(iframe_src, timeout=MAX_TIMEOUT)
        video_response.raise_for_status()

        download_url_match = DOWNLOAD_URL_REGEX.search(video_response.text)
        if download_url_match:
            yield map_to_server(episode, download_url_match.group(1))
        return None


if __name__ == "__main__":
    from ..utils.debug import test_anime_provider

    test_anime_provider(AnimeUnity)
