"""An abstraction over all providers offering added features with a simple and well typed api"""

import importlib
import logging
import os
from typing import TYPE_CHECKING

from .allanime.constants import SERVERS_AVAILABLE as ALLANIME_SERVERS
from .animepahe.constants import SERVERS_AVAILABLE as ANIMEPAHE_SERVERS
from .hianime.constants import SERVERS_AVAILABLE as HIANIME_SERVERS
from httpx import Client, AsyncClient
from yt_dlp.utils.networking import random_user_agent

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .types import Anime, SearchResults, Server

logger = logging.getLogger(__name__)

PROVIDERS_AVAILABLE = {
    "allanime": "api.AllAnime",
    "animepahe": "api.AnimePahe",
    "hianime": "api.HiAnime",
    "nyaa": "api.Nyaa",
    "yugen": "api.Yugen",
}
SERVERS_AVAILABLE = ["top", *ALLANIME_SERVERS, *ANIMEPAHE_SERVERS, *HIANIME_SERVERS]


class AnimeProvider:
    """An abstraction over all anime providers"""

    PROVIDERS = list(PROVIDERS_AVAILABLE.keys())
    provider = PROVIDERS[0]

    def __init__(
        self,
        provider,
        cache_requests=os.environ.get("FASTANIME_CACHE_REQUESTS", "false"),
        use_persistent_provider_store=os.environ.get(
            "FASTANIME_USE_PERSISTENT_PROVIDER_STORE", "false"
        ),
        dynamic=False,
        retries=0,
    ) -> None:
        self.provider = provider
        self.dynamic = dynamic
        self.retries = retries
        self.cache_requests = cache_requests
        self.use_persistent_provider_store = use_persistent_provider_store
        self.lazyload_provider(self.provider)

    def setup_httpx_client(self) -> Client:
        """Sets up a httpx client with a random user agent"""
        client = Client(headers={"User-Agent": random_user_agent()})
        return client

    def setup_httpx_async_client(self) -> AsyncClient:
        """Sets up a httpx client with a random user agent"""
        client = AsyncClient(headers={"User-Agent": random_user_agent()})
        return client

    def lazyload_provider(self, provider):
        """updates the current provider being used"""
        try:
            self.anime_provider.session.kill_connection_to_db()
        except Exception:
            pass
        _, anime_provider_cls_name = PROVIDERS_AVAILABLE[provider].split(".", 1)
        package = f"fastanime.libs.anime_provider.{provider}"
        provider_api = importlib.import_module(".api", package)
        anime_provider = getattr(provider_api, anime_provider_cls_name)
        self.anime_provider = anime_provider(
            self.cache_requests, self.use_persistent_provider_store
        )

    def search_for_anime(
        self, search_keywords, translation_type, **kwargs
    ) -> "SearchResults | None":
        """core abstraction over all providers search functionality

        Args:
            user_query ([TODO:parameter]): [TODO:description]
            translation_type ([TODO:parameter]): [TODO:description]
            nsfw ([TODO:parameter]): [TODO:description]
            unknown ([TODO:parameter]): [TODO:description]
            anilist_obj: [TODO:description]

        Returns:
            [TODO:return]
        """
        anime_provider = self.anime_provider
        results = anime_provider.search_for_anime(
            search_keywords, translation_type, **kwargs
        )

        return results

    def get_anime(
        self,
        anime_id: str,
        **kwargs,
    ) -> "Anime | None":
        """core abstraction over getting info of an anime from all providers

        Args:
            anime_id: [TODO:description]
            anilist_obj: [TODO:description]

        Returns:
            [TODO:return]
        """
        anime_provider = self.anime_provider
        results = anime_provider.get_anime(anime_id, **kwargs)

        return results

    def get_episode_streams(
        self,
        anime_id,
        episode: str,
        translation_type: str,
        **kwargs,
    ) -> "Iterator[Server] | None":
        """core abstractions for getting juicy streams from all providers

        Args:
            anime ([TODO:parameter]): [TODO:description]
            episode: [TODO:description]
            translation_type: [TODO:description]
            anilist_obj: [TODO:description]

        Returns:
            [TODO:return]
        """
        anime_provider = self.anime_provider
        results = anime_provider.get_episode_streams(
            anime_id, episode, translation_type, **kwargs
        )
        return results
