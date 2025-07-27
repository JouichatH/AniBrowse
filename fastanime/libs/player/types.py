from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerResult:
    episode: str
    stop_time: str | None = None
    total_time: str | None = None
