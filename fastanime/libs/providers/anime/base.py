from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Dict

from httpx import Client

from .params import AnimeParams, EpisodeStreamsParams, SearchParams

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .types import Anime, SearchResults, Server


class AnimeProvider(ABC):
    HEADERS: ClassVar[Dict[str, str]]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "HEADERS"):
            raise TypeError(
                f"Subclasses of AnimeProvider must define a 'HEADERS' class attribute."
            )

    def __init__(self, client: Client) -> None:
        self.client = client

    @abstractmethod
    def search(self, params: SearchParams) -> "SearchResults | None":
        pass

    @abstractmethod
    def get(self, params: AnimeParams) -> "Anime | None":
        pass

    @abstractmethod
    def episode_streams(
        self, params: EpisodeStreamsParams
    ) -> "Iterator[Server] | None":
        pass
