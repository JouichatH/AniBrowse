from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerResult:
    """
    Represents the result of a completed playback session.

    Attributes:
        stop_time: The timestamp where playback stopped (e.g., "00:15:30").
        total_time: The total duration of the media (e.g., "00:23:45").
    """

    episode: str | None = None
    stop_time: str | None = None
    total_time: str | None = None
