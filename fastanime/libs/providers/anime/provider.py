import importlib
import logging

from httpx import Client
from yt_dlp.utils.networking import random_user_agent

from .allanime.constants import SERVERS_AVAILABLE as ALLANIME_SERVERS
from .animepahe.constants import SERVERS_AVAILABLE as ANIMEPAHE_SERVERS
from .base import BaseAnimeProvider
from .hianime.constants import SERVERS_AVAILABLE as HIANIME_SERVERS

logger = logging.getLogger(__name__)

PROVIDERS_AVAILABLE = {
    "allanime": "provider.AllAnime",
    "animepahe": "provider.AnimePahe",
    "hianime": "provider.HiAnime",
    "nyaa": "provider.Nyaa",
    "yugen": "provider.Yugen",
}
SERVERS_AVAILABLE = ["TOP", *ALLANIME_SERVERS, *ANIMEPAHE_SERVERS, *HIANIME_SERVERS]


class AnimeProviderFactory:
    """Factory for creating anime provider instances."""

    @staticmethod
    def create(provider_name: str) -> BaseAnimeProvider:
        """
        Dynamically creates an instance of the specified anime provider.

        This method imports the necessary provider module, instantiates its main class,
        and injects a pre-configured HTTP client.

        Args:
            provider_name: The name of the provider to create (e.g., 'allanime').

        Returns:
            An instance of a class that inherits from BaseProvider.

        Raises:
            ValueError: If the provider_name is not supported.
            ImportError: If the provider module or class cannot be found.
        """
        if provider_name not in PROVIDERS_AVAILABLE:
            raise ValueError(
                f"Unsupported provider: '{provider_name}'. Supported providers are: "
                f"{list(PROVIDERS_AVAILABLE.keys())}"
            )

        # Correctly determine module and class name from the map
        import_path = PROVIDERS_AVAILABLE[provider_name]
        module_name, class_name = import_path.split(".", 1)

        # Construct the full package path for dynamic import
        package_path = f"fastanime.libs.providers.anime.{provider_name}"

        try:
            provider_module = importlib.import_module(f".{module_name}", package_path)
            provider_class = getattr(provider_module, class_name)
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to load provider '{provider_name}': {e}")
            raise ImportError(
                f"Could not load provider '{provider_name}'. "
                "Check the module path and class name in PROVIDERS_AVAILABLE."
            ) from e

        # Each provider class requires an httpx.Client, which we set up here.
        client = Client(
            headers={"User-Agent": random_user_agent(), **provider_class.HEADERS}
        )

        return provider_class(client)


# Simple alias for ease of use, consistent with other factories in the codebase.
create_provider = AnimeProviderFactory.create
