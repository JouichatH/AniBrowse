from abc import ABC, abstractmethod

from .params import PlayerParams
from .types import PlayerResult


class BasePlayer(ABC):
    """
    Abstract Base Class defining the contract for all media players.
    """

    @abstractmethod
    def play(self, params: PlayerParams) -> PlayerResult:
        """
        Plays the given media URL.
        """
        pass
