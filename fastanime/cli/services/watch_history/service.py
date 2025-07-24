import logging
from typing import Optional

from ....core.config.model import AppConfig
from ....libs.api.base import BaseApiClient
from ....libs.api.params import UpdateUserMediaListEntryParams
from ....libs.api.types import MediaItem, UserMediaListStatus
from ....libs.players.types import PlayerResult
from ..registry import MediaRegistryService

logger = logging.getLogger(__name__)


# TODO: Implement stuff like syncing btw local and remote
class WatchHistoryService:
    def __init__(
        self,
        config: AppConfig,
        media_registry: MediaRegistryService,
        media_api: Optional[BaseApiClient] = None,
    ):
        self.config = config
        self.media_registry = media_registry
        self.media_api = media_api

    def track(self, media_item: MediaItem, episode: str, player_result: PlayerResult):
        status = None
        self.media_registry.update_media_index_entry(
            media_id=media_item.id,
            watched=True,
            media_item=media_item,
            last_watch_position=player_result.stop_time,
            total_duration=player_result.total_time,
            progress=episode,
            status=status,
        )

        if self.media_api and self.media_api.is_authenticated():
            self.media_api.update_list_entry(
                UpdateUserMediaListEntryParams(
                    media_id=media_item.id,
                    progress=episode,
                    status=status,
                )
            )

    def update(
        self,
        media_item: MediaItem,
        progress: Optional[str] = None,
        status: Optional[UserMediaListStatus] = None,
        score: Optional[float] = None,
        notes: Optional[str] = None,
    ):
        self.media_registry.update_media_index_entry(
            media_id=media_item.id,
            media_item=media_item,
            progress=progress,
            status=status,
            score=score,
            notes=notes,
        )

        if self.media_api and self.media_api.is_authenticated():
            self.media_api.update_list_entry(
                UpdateUserMediaListEntryParams(
                    media_id=media_item.id,
                    status=status,
                    score=score,
                    progress=progress,
                )
            )
