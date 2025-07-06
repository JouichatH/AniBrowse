from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ...core.config import AppConfig
    from ...libs.api.base import BaseApiClient
    from ...libs.api.types import Anime, SearchResult, Server, UserProfile
    from ...libs.players.base import BasePlayer
    from ...libs.selector.base import BaseSelector

logger = logging.getLogger(__name__)


# --- Nested State Models (Unchanged) ---
class AnilistState(BaseModel):
    results_data: Optional[dict] = None
    selected_anime: Optional[dict] = (
        None  # Using dict for AnilistBaseMediaDataSchema for now
    )


class ProviderState(BaseModel):
    selected_search_result: Optional[SearchResult] = None
    anime_details: Optional[Anime] = None
    current_episode: Optional[str] = None
    current_server: Optional[Server] = None

    class Config:
        arbitrary_types_allowed = True


class NavigationState(BaseModel):
    current_page: int = 1
    history_stack_class_names: list[str] = Field(default_factory=list)


class TrackingState(BaseModel):
    progress_mode: str = "prompt"


class SessionState(BaseModel):
    anilist: AnilistState = Field(default_factory=AnilistState)
    provider: ProviderState = Field(default_factory=ProviderState)
    navigation: NavigationState = Field(default_factory=NavigationState)
    tracking: TrackingState = Field(default_factory=TrackingState)

    class Config:
        arbitrary_types_allowed = True


class Session:
    def __init__(self, config: AppConfig) -> None:
        self.config: AppConfig = config
        self.state: SessionState = SessionState()
        self.is_running: bool = True
        self.user_profile: Optional[UserProfile] = None
        self._initialize_components()

    def _initialize_components(self) -> None:
        from ...cli.auth.manager import CredentialsManager
        from ...libs.api.factory import create_api_client
        from ...libs.players import create_player
        from ...libs.selector import create_selector

        logger.debug("Initializing session components...")
        self.selector: BaseSelector = create_selector(self.config)
        self.provider: BaseAnimeProvider = create_provider(self.config.general.provider)
        self.player: BasePlayer = create_player(self.config.stream.player, self.config)

        # Instantiate and use the API factory
        self.api_client: BaseApiClient = create_api_client("anilist", self.config)

        # Load credentials and authenticate the API client
        manager = CredentialsManager()
        user_data = manager.load_user_profile()
        if user_data and (token := user_data.get("token")):
            self.user_profile = self.api_client.authenticate(token)
            if not self.user_profile:
                logger.warning(
                    "Loaded token is invalid or expired. User is not logged in."
                )

    def change_provider(self, provider_name: str) -> None:
        from ...libs.anime.provider import create_provider

        self.config.general.provider = provider_name
        self.provider = create_provider(provider_name)

    def change_player(self, player_name: str) -> None:
        from ...libs.players import create_player

        self.config.stream.player = player_name
        self.player = create_player(player_name, self.config)

    def stop(self) -> None:
        self.is_running = False
