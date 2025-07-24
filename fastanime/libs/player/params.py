from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerParams:
    url: str
    title: str
    syncplay: bool = False
    subtitles: list[str] | None = None
    headers: dict[str, str] | None = None
    start_time: str | None = None
