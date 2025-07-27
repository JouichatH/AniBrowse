from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class PlayerParams:
    url: str
    title: str
    query: str
    episode: str
    syncplay: bool = False
    subtitles: list[str] | None = None
    headers: dict[str, str] | None = None
    start_time: str | None = None
