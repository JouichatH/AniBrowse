from typing import TYPE_CHECKING

# from .vlc.player import VlcPlayer  # When you create it
# from .syncplay.player import SyncplayPlayer # When you create it
from ...core.config import AppConfig
from .base import BasePlayer

PLAYERS = ["mpv", "vlc", "syncplay"]


class PlayerFactory:
    @staticmethod
    def create(player_name: str, config: AppConfig) -> BasePlayer:
        """
        Factory method to create a player instance based on its name.

        Args:
            player_name: The name of the player (e.g., 'mpv', 'vlc').
            config: The full application configuration object.

        Returns:
            An instance of a class that inherits from BasePlayer.

        Raises:
            ValueError: If the player_name is not supported.
        """

        if player_name not in PLAYERS:
            raise ValueError(
                f"Unsupported player: '{player_name}'. Supported players are: {PLAYERS}"
            )

        if player_name == "mpv":
            from .mpv import MpvPlayer

            return MpvPlayer(config.mpv)
        raise NotImplementedError(
            f"Configuration logic for player '{player_name}' not implemented in factory."
        )


create_player = PlayerFactory.create
