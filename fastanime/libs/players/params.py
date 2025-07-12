from dataclasses import dataclass


@dataclass
class Subtitle:
    url: str
    language: str | None = None


@dataclass(frozen=True)
class PlayerParams:
    url: str
    title: str
    subtitles: list[Subtitle] | None = None
    headers: dict[str, str] | None = None
    start_time: str | None = None
