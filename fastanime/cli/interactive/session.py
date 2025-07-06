from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ...core.config import AppConfig
    from ...libs.anilist.api import AniListApi
    from ...libs.anilist.types import AnilistBaseMediaDataSchema
    from ...libs.anime.provider import AnimeProvider

    # Import the dataclasses for type hinting
    from ...libs.anime.types import Anime, SearchResult, SearchResults, Server
    from ...libs.players.base import BasePlayer
    from ...libs.selector.base import BaseSelector

logger = logging.getLogger(__name__)


# --- Nested State Models ---
class AnilistState(BaseModel):
    """Holds state related to AniList data and selections."""

    results_data: dict | None = None
    selected_anime: Optional[AnilistBaseMediaDataSchema] = None


class ProviderState(BaseModel):
    """Holds state related to the current anime provider, using specific dataclasses."""

    search_results: Optional[SearchResults] = None
    selected_search_result: Optional[SearchResult] = None
    anime_details: Optional[Anime] = None
    current_episode: Optional[str] = None
    current_server: Optional[Server] = None


class NavigationState(BaseModel):
    """Holds state related to the UI navigation stack."""

    current_page: int = 1
    history_stack_class_names: list[str] = Field(default_factory=list)


class TrackingState(BaseModel):
    """Holds state for user progress tracking preferences."""

    progress_mode: str = "prompt"


# --- Top-Level SessionState ---
class SessionState(BaseModel):
    """The root model for all serializable runtime state."""

    anilist: AnilistState = Field(default_factory=AnilistState)
    provider: ProviderState = Field(default_factory=ProviderState)
    navigation: NavigationState = Field(default_factory=NavigationState)
    tracking: TrackingState = Field(default_factory=TrackingState)

    class Config:
        arbitrary_types_allowed = True


class Session:
    """
    Manages the entire runtime session for the interactive anilist command.
    """

    def __init__(self, config: AppConfig, anilist_client: AniListApi) -> None:
        self.config: AppConfig = config
        self.state: SessionState = SessionState()
        self.is_running: bool = True
        self.anilist: AniListApi = anilist_client
        self._initialize_components()

    def _initialize_components(self) -> None:
        """Creates instances of core components based on the current config."""
        from ...libs.anime.provider import create_provider
        from ...libs.players import create_player
        from ...libs.selector import create_selector

        logger.debug("Initializing session components from configuration...")
        self.selector: BaseSelector = create_selector(self.config)
        self.provider: AnimeProvider = create_provider(self.config.general.provider)
        self.player: BasePlayer = create_player(self.config.stream.player, self.config)

    def change_provider(self, provider_name: str) -> None:
        from ...libs.anime.provider import create_provider

        self.config.general.provider = provider_name
        self.provider = create_provider(provider_name)
        logger.info(f"Provider changed to: {self.provider.__class__.__name__}")

    def change_player(self, player_name: str) -> None:
        from ...libs.players import create_player

        self.config.stream.player = player_name
        self.player = create_player(player_name, self.config)
        logger.info(f"Player changed to: {self.player.__class__.__name__}")

    def stop(self) -> None:
        self.is_running = False
