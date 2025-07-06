import importlib
import logging
from typing import TYPE_CHECKING

from yt_dlp.utils.networking import random_user_agent

from .allanime.constants import SERVERS_AVAILABLE as ALLANIME_SERVERS
from .animepahe.constants import SERVERS_AVAILABLE as ANIMEPAHE_SERVERS
from .base import AnimeProvider as Base
from .hianime.constants import SERVERS_AVAILABLE as HIANIME_SERVERS
from .params import AnimeParams, EpisodeStreamsParams, SearchParams

if TYPE_CHECKING:
    from collections.abc import Iterator

    from httpx import AsyncClient, Client

    from .types import Anime, SearchResults, Server

logger = logging.getLogger(__name__)

PROVIDERS_AVAILABLE = {
    "allanime": "provider.AllAnime",
    "animepahe": "provider.AnimePahe",
    "hianime": "provider.HiAnime",
    "nyaa": "provider.Nyaa",
    "yugen": "provider.Yugen",
}
SERVERS_AVAILABLE = ["TOP", *ALLANIME_SERVERS, *ANIMEPAHE_SERVERS, *HIANIME_SERVERS]


class AnimeProvider:
    """An abstraction over all anime providers"""

    PROVIDERS = list(PROVIDERS_AVAILABLE.keys())
    current_provider_name = PROVIDERS[0]
    current_provider: Base

    def __init__(
        self,
        provider: str,
        cache_requests=False,
        use_persistent_provider_store=False,
        dynamic=False,
        retries=0,
    ) -> None:
        self.current_provider_name = provider
        self.dynamic = dynamic
        self.retries = retries
        self.cache_requests = cache_requests
        self.use_persistent_provider_store = use_persistent_provider_store
        self.lazyload(self.current_provider_name)

    def search(self, params: SearchParams) -> "SearchResults | None":
        results = self.current_provider.search(params)

        return results

    def get(self, params: AnimeParams) -> "Anime | None":
        results = self.current_provider.get(params)

        return results

    def episode_streams(
        self, params: EpisodeStreamsParams
    ) -> "Iterator[Server] | None":
        results = self.current_provider.episode_streams(params)
        return results

    def setup_httpx_client(self, headers) -> "Client":
        """Sets up a httpx client with a random user agent"""
        client = Client(headers={"User-Agent": random_user_agent(), **headers})
        return client

    def setup_httpx_async_client(self) -> "AsyncClient":
        """Sets up a httpx client with a random user agent"""
        client = AsyncClient(headers={"User-Agent": random_user_agent()})
        return client

    def lazyload(self, provider):
        _, anime_provider_cls_name = PROVIDERS_AVAILABLE[provider].split(".", 1)
        package = f"fastanime.libs.providers.anime.{provider}"
        provider_api = importlib.import_module(".api", package)
        anime_provider = getattr(provider_api, anime_provider_cls_name)
        client = self.setup_httpx_client(anime_provider.HEADERS)
        self.current_provider = anime_provider(client)
