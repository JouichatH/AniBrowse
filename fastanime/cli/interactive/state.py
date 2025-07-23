from enum import Enum, auto
from typing import Dict, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from ...libs.api.params import MediaSearchParams, UserMediaListSearchParams
from ...libs.api.types import MediaItem, PageInfo
from ...libs.providers.anime.types import Anime, SearchResults, Server


# TODO: is internal directive a good name
class InternalDirective(Enum):
    BACK = auto()

    BACKX2 = auto()

    BACKX3 = auto()

    EXIT = auto()

    CONFIG_EDIT = auto()

    CONTINUE = auto()


class MenuName(Enum):
    MAIN = "MAIN"
    AUTH = "AUTH"
    EPISODES = "EPISODES"
    RESULTS = "RESULTS"
    SERVERS = "SERVERS"
    WATCH_HISTORY = "WATCH_HISTORY"
    PROVIDER_SEARCH = "PROVIDER_SEARCH"
    PLAYER_CONTROLS = "PLAYER_CONTROLS"
    USER_MEDIA_LIST = "USER_MEDIA_LIST"
    SESSION_MANAGEMENT = "SESSION_MANAGEMENT"


class StateModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class MediaApiState(StateModel):
    search_result: Optional[Dict[int, MediaItem]] = None
    search_params: Optional[Union[MediaSearchParams, UserMediaListSearchParams]] = None
    page_info: Optional[PageInfo] = None
    media_id: Optional[int] = None

    @property
    def media_item(self) -> Optional[MediaItem]:
        if self.search_result and self.media_id:
            return self.search_result[self.media_id]


class ProviderState(StateModel):
    search_results: Optional[SearchResults] = None
    anime: Optional[Anime] = None
    episode: Optional[str] = None
    servers: Optional[Dict[str, Server]] = None
    server_name: Optional[str] = None

    @property
    def server(self) -> Optional[Server]:
        if self.servers and self.server_name:
            return self.servers[self.server_name]


class State(StateModel):
    menu_name: MenuName
    provider: ProviderState = Field(default_factory=ProviderState)
    media_api: MediaApiState = Field(default_factory=MediaApiState)
