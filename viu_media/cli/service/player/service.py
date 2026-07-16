import json
import logging
import os
from typing import Optional

from ....core.config import AppConfig
from ....core.constants import APP_CACHE_DIR
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


def _skip_json_path() -> str:
    """Stable, app-owned path the viu_skip Lua polls for AniSkip intervals."""
    return str(APP_CACHE_DIR / "skip.json")


def _write_skip_json(
    path: str,
    op: Optional[tuple[float, float]],
    ed: Optional[tuple[float, float]],
    done: bool,
) -> None:
    """Atomically write the AniSkip interval file (best-effort).

    ``op``/``ed`` are ``[start, end]`` or null; ``done`` tells the Lua the fetch
    has finished so it can stop polling (whether or not intervals were found).
    """
    payload = {
        "op": [op[0], op[1]] if op else None,
        "ed": [ed[0], ed[1]] if ed else None,
        "done": done,
    }
    try:
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp, path)
    except OSError as e:  # a disk hiccup here must never break playback
        logger.debug("could not write skip json: %s", e)


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
        """Enable opening/ending skip and deliver AniSkip intervals via file.

        AniSkip is kept OFF the launch path: mpv spawns immediately with skip
        enabled (so the Lua's chapter fallback acts at once), and the intervals
        are fetched in a background thread that writes them to ``skip.json``,
        which the Lua polls. They arrive a moment after launch — long before the
        opening plays. Best-effort: any failure just leaves skip on chapter-only.
        """
        import dataclasses
        import threading

        cfg = self.app_config.stream
        if not (cfg.opening_skip or cfg.ending_skip):
            return params

        mal_id = getattr(media_item, "id_mal", None) if media_item else None
        skip_path = _skip_json_path()
        # Clear any previous episode's intervals so the Lua never reads stale data.
        # With no MAL id there is nothing to fetch, so mark done immediately.
        _write_skip_json(skip_path, op=None, ed=None, done=mal_id is None)

        if mal_id:
            episode = params.episode
            op_on, ed_on = cfg.opening_skip, cfg.ending_skip

            def _fetch_skip() -> None:
                op = ed = None
                try:
                    from .aniskip import fetch_skip_times

                    for interval in fetch_skip_times(mal_id, episode):
                        if interval.kind == "op" and op_on:
                            op = (interval.start, interval.end)
                        elif interval.kind == "ed" and ed_on:
                            ed = (interval.start, interval.end)
                except Exception as e:  # noqa: BLE001 - skip is best-effort
                    logger.debug("skip fetch failed for ep %s: %s", episode, e)
                _write_skip_json(skip_path, op=op, ed=ed, done=True)

            threading.Thread(target=_fetch_skip, daemon=True).start()

        return dataclasses.replace(
            params,
            skip_op=None,
            skip_ed=None,
            skip_op_enabled=cfg.opening_skip,
            skip_ed_enabled=cfg.ending_skip,
            skip_json=skip_path,
        )

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
