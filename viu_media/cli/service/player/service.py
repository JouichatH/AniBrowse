import logging
from typing import Optional

from ....core.config import AppConfig
from ....core.exceptions import ViuError
from ....libs.media_api.types import MediaItem
from ....libs.player.base import BasePlayer
from ....libs.player.params import PlayerParams
from ....libs.player.player import create_player
from ....libs.player.types import PlayerResult
from ....libs.provider.anime.base import BaseAnimeProvider
from ....libs.provider.anime.types import Anime
from ..registry import MediaRegistryService

logger = logging.getLogger(__name__)


class PlayerService:
    app_config: AppConfig
    provider: BaseAnimeProvider
    player: BasePlayer
    registry: Optional[MediaRegistryService] = None
    local: bool = False

    def __init__(
        self,
        app_config: AppConfig,
        provider: BaseAnimeProvider,
        registry: Optional[MediaRegistryService] = None,
    ):
        self.app_config = app_config
        self.provider = provider
        self.registry = registry
        self.player = create_player(app_config)

    def play(
        self,
        params: PlayerParams,
        anime: Optional[Anime] = None,
        media_item: Optional[MediaItem] = None,
        local: bool = False,
    ) -> PlayerResult:
        self.local = local
        if self.app_config.stream.use_ipc:
            if anime or self.registry:
                return self._play_with_ipc(params, anime, media_item)
            else:
                logger.warning(
                    f"Ipc player won't be used since Anime Object has not been given for url={params.url}"
                )
        # Clean (non-IPC) path: bake AniSkip intervals into the launch so
        # opening/ending skip still works without a persistent IPC connection.
        return self.player.play(self._with_skip(params, media_item))

    def _with_skip(
        self, params: PlayerParams, media_item: Optional[MediaItem]
    ) -> PlayerParams:
        """Attach opening/ending skip intervals to ``params`` when enabled.

        Best-effort: any failure (no MAL id, network hiccup, disabled) just
        returns the params unchanged so playback is never blocked.
        """
        import dataclasses

        cfg = self.app_config.stream
        if not (cfg.opening_skip or cfg.ending_skip):
            return params
        mal_id = getattr(media_item, "id_mal", None) if media_item else None
        if not mal_id:
            return params
        try:
            from .aniskip import fetch_skip_times

            intervals = fetch_skip_times(mal_id, params.episode)
        except Exception as e:  # noqa: BLE001 - skip is best-effort
            logger.debug("skip fetch failed for ep %s: %s", params.episode, e)
            return params

        skip_op = skip_ed = None
        for interval in intervals:
            if interval.kind == "op" and cfg.opening_skip:
                skip_op = (interval.start, interval.end)
            elif interval.kind == "ed" and cfg.ending_skip:
                skip_ed = (interval.start, interval.end)
        if skip_op is None and skip_ed is None:
            return params
        return dataclasses.replace(params, skip_op=skip_op, skip_ed=skip_ed)

    def _play_with_ipc(
        self,
        params: PlayerParams,
        anime: Optional[Anime] = None,
        media_item: Optional[MediaItem] = None,
    ) -> PlayerResult:
        if self.app_config.stream.player == "mpv":
            from .ipc.mpv import MpvIPCPlayer

            registry = self.registry if self.local else None
            return MpvIPCPlayer(self.app_config.stream).play(
                self.player, params, self.provider, anime, registry, media_item
            )
        else:
            raise ViuError("Not implemented")
