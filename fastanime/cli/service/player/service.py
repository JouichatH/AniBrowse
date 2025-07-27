from typing import Optional

from ....core.config import AppConfig
from ....core.exceptions import FastAnimeError
from ....libs.media_api.types import MediaItem
from ....libs.player.base import BasePlayer
from ....libs.player.params import PlayerParams
from ....libs.player.player import create_player
from ....libs.player.types import PlayerResult
from ....libs.provider.anime.base import BaseAnimeProvider
from ....libs.provider.anime.types import Anime


class PlayerService:
    app_config: AppConfig
    provider: BaseAnimeProvider
    player: BasePlayer

    def __init__(self, app_config: AppConfig, provider: BaseAnimeProvider):
        self.app_config = app_config
        self.provider = provider
        self.player = create_player(app_config)

    def play(
        self, params: PlayerParams, anime: Anime, media_item: Optional[MediaItem] = None
    ) -> PlayerResult:
        if self.app_config.stream.use_ipc:
            return self._play_with_ipc(params, anime, media_item)
        else:
            return self.player.play(params)

    def _play_with_ipc(
        self, params: PlayerParams, anime: Anime, media_item: Optional[MediaItem] = None
    ) -> PlayerResult:
        if self.app_config.stream.player == "mpv":
            from .ipc.mpv import MpvIPCPlayer

            return MpvIPCPlayer(self.app_config.stream).play(
                self.player, params, self.provider, anime, media_item
            )
        else:
            raise FastAnimeError("Not implemented")
