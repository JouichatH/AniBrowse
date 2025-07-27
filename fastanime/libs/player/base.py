import subprocess
from abc import ABC, abstractmethod

from ...core.config import StreamConfig
from .params import PlayerParams
from .types import PlayerResult


class BasePlayer(ABC):
    """
    Abstract Base Class defining the contract for all media players.
    """

    def __init__(self, config: StreamConfig):
        self.stream_config = config

    @abstractmethod
    def play(self, params: PlayerParams) -> PlayerResult:
        """
        Plays the given media URL.
        """
        pass

    @abstractmethod
    def play_with_ipc(self, params: PlayerParams, socket_path: str) -> subprocess.Popen:
        """Stream using IPC player for enhanced features."""
