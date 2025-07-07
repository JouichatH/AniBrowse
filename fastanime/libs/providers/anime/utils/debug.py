import functools
import logging
import os
from typing import Type

from ..base import BaseAnimeProvider

logger = logging.getLogger(__name__)


def debug_provider(provider_function):
    @functools.wraps(provider_function)
    def _provider_function_wrapper(self, *args, **kwargs):
        provider_name = self.__class__.__name__.upper()
        if not os.environ.get("FASTANIME_DEBUG"):
            try:
                return provider_function(self, *args, **kwargs)
            except Exception as e:
                logger.error(f"[{provider_name}@{provider_function.__name__}]: {e}")
        else:
            return provider_function(self, *args, **kwargs)

    return _provider_function_wrapper


def test_anime_provider(AnimeProvider: Type[BaseAnimeProvider]):
    from httpx import Client
    from yt_dlp.utils.networking import random_user_agent

    from .....core.constants import APP_ASCII_ART
    from ..params import AnimeParams, EpisodeStreamsParams, SearchParams

    anime_provider = AnimeProvider(
        Client(headers={"User-Agent": random_user_agent(), **AnimeProvider.HEADERS})
    )
    print(APP_ASCII_ART)
    query = input("What anime would you like to stream: ")
    search_results = anime_provider.search(SearchParams(query=query))
    if not search_results:
        return
    for i, search_result in enumerate(search_results.results):
        print(f"{i + 1}: {search_result.title}")
    result = search_results.results[
        int(input(f"Select result (1-{len(search_results.results)}): ")) - 1
    ]
    anime = anime_provider.get(AnimeParams(id=result.id))

    if not anime:
        return
    translation_type = input("Preferred Translation Type: [dub,sub,raw]: ")
    for episode in getattr(anime.episodes, translation_type):
        print(episode)
    episode_number = input("What episode do you wish to watch: ")
    episode_streams = anime_provider.episode_streams(
        EpisodeStreamsParams(
            anime_id=anime.id,
            episode=episode_number,
            translation_type=translation_type,  # type:ignore
        )
    )

    if not episode_streams:
        return
    print(list(episode_streams))
