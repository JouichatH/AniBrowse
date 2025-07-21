from enum import Enum, auto
from typing import Iterator, List, Literal, Optional

from pydantic import BaseModel, ConfigDict

from ...libs.api.params import ApiSearchParams, UserListParams  # Add this import
from ...libs.api.types import (
    MediaItem,
    MediaSearchResult,
    MediaStatus,
    UserListStatusType,
)
from ...libs.players.types import PlayerResult
from ...libs.providers.anime.types import Anime, SearchResults, Server


class ControlFlow(Enum):
    """
    Represents special commands to control the session loop instead of
    transitioning to a new state. This provides a clear, type-safe alternative
    to using magic strings.
    """

    BACK = auto()
    """Pop the current state from history and return to the previous one."""

    EXIT = auto()
    """Terminate the interactive session gracefully."""

    CONFIG_EDIT = auto()
    """Reload the application configuration and re-initialize the context."""

    CONTINUE = auto()
    """
    Stay in the current menu. This is useful for actions that don't
    change the state but should not exit the menu (e.g., displaying an error).
    """


# ==============================================================================
# Nested State Models
# ==============================================================================


class ProviderState(BaseModel):
    """
    An immutable snapshot of data related to the anime provider.
    This includes search results, the selected anime's full details,
    and the latest fetched episode streams.
    """

    search_results: Optional[SearchResults] = None
    anime: Optional[Anime] = None
    episode_streams: Optional[Iterator[Server]] = None
    episode_number: Optional[str] = None
    last_player_result: Optional[PlayerResult] = None
    servers: Optional[List[Server]] = None
    selected_server: Optional[Server] = None

    model_config = ConfigDict(
        frozen=True,
        # Required to allow complex types like iterators in the model.
        arbitrary_types_allowed=True,
    )


class MediaApiState(BaseModel):
    """
    An immutable snapshot of data related to the metadata API (e.g., AniList).
    This includes search results and the full details of a selected media item.
    """

    search_results: Optional[MediaSearchResult] = None
    search_results_type: Optional[Literal["MEDIA_LIST", "USER_MEDIA_LIST"]] = None
    sort: Optional[str] = None
    query: Optional[str] = None
    user_media_status: Optional[UserListStatusType] = None
    media_status: Optional[MediaStatus] = None
    anime: Optional[MediaItem] = None

    # Add pagination support: store original search parameters to enable page navigation
    original_api_params: Optional[ApiSearchParams] = None
    original_user_list_params: Optional[UserListParams] = None

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)


# ==============================================================================
# Root State Model
# ==============================================================================


class State(BaseModel):
    """
    Represents the complete, immutable state of the interactive UI at a single
    point in time. A new State object is created for each transition.

    Attributes:
        menu_name: The name of the menu function (e.g., 'MAIN', 'MEDIA_RESULTS')
                   that should be rendered for this state.
        provider:  Nested state for data from the anime provider.
        media_api: Nested state for data from the metadata API (AniList).
    """

    menu_name: str
    provider: ProviderState = ProviderState()
    media_api: MediaApiState = MediaApiState()

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
