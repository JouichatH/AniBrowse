"""
Defines the PlayerParams dataclass, which encapsulates all parameters required to launch a media player session.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class PlayerParams:
    """
    Parameters for launching a media player session.

    Attributes:
        url: The media URL to play.
        title: The title to display in the player.
        query: The original search query or context.
        episode: The episode identifier or label.
        syncplay: Whether to enable syncplay (synchronized playback).
        subtitles: List of subtitle file paths or URLs.
        headers: HTTP headers to include in the request.
        start_time: The time offset to start playback from.
    """

    url: str
    title: str
    query: str
    episode: str
    syncplay: bool = False
    subtitles: list[str] | None = None
    headers: dict[str, str] | None = None
    start_time: str | None = None
    # AniSkip opening/ending intervals in seconds, (start, end), for the clean
    # (non-IPC) path to bake into mpv at launch via the viu_skip Lua script.
    skip_op: tuple[float, float] | None = None
    skip_ed: tuple[float, float] | None = None
    # Whether opening/ending skip is enabled (drives interval AND chapter-based
    # skipping in the Lua, independently of whether AniSkip returned intervals).
    skip_op_enabled: bool = False
    skip_ed_enabled: bool = False
