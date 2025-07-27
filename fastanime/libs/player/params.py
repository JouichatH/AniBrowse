from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Literal, Optional

if TYPE_CHECKING:
    from ..provider.anime.base import BaseAnimeProvider
    from ..provider.anime.types import Anime


@dataclass(frozen=True)
class PlayerParams:
    url: str
    title: str
    syncplay: bool = False
    subtitles: list[str] | None = None
    headers: dict[str, str] | None = None
    start_time: str | None = None

    # IPC player specific parameters for episode navigation
    anime_provider: Optional["BaseAnimeProvider"] = None
    current_anime: Optional["Anime"] = None
    available_episodes: Optional[List[str]] = None
    current_episode: Optional[str] = None
    current_anime_id: Optional[str] = None
    current_anime_title: Optional[str] = None
    current_translation_type: Optional[Literal["sub", "dub"]] = None
