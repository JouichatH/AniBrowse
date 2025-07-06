from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from ..providers.anime.types import Subtitle


@dataclass(frozen=True)
class PlayerResult:
    """
    Represents the result of a completed playback session.

    Attributes:
        stop_time: The timestamp where playback stopped (e.g., "00:15:30").
        total_time: The total duration of the media (e.g., "00:23:45").
    """

    stop_time: str | None = None
    total_time: str | None = None


class BasePlayer(ABC):
    """
    Abstract Base Class defining the contract for all media players.
    """

    @abstractmethod
    def play(
        self,
        url: str,
        title: str,
        subtitles: List["Subtitle"] | None = None,
        headers: dict | None = None,
        start_time: str = "0",
    ) -> PlayerResult:
        """
        Plays the given media URL.

        Args:
            url: The stream URL to play.
            title: The title to display in the player window.
            subtitles: A list of subtitle objects.
            headers: Any required HTTP headers for the stream.
            start_time: The timestamp to start playback from (e.g., "00:10:30").

        Returns:
            A tuple containing (stop_time, total_time) as strings.
        """
        pass
