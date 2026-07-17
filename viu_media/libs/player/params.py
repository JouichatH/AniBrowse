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
    # (non-IPC) path to bake into mpv at launch via the ani_skip Lua script.
    skip_op: tuple[float, float] | None = None
    skip_ed: tuple[float, float] | None = None
    # Whether opening/ending skip is enabled (drives interval AND chapter-based
    # skipping in the Lua, independently of whether AniSkip returned intervals).
    skip_op_enabled: bool = False
    skip_ed_enabled: bool = False
    # Path to a JSON file of alternate servers (name/url/headers/quality) that the
    # ani_skip Lua reads for its in-player server-switch menu (Ctrl+S). The app
    # (re)writes this file as background server resolution completes, so the menu
    # can switch streams without leaving mpv. Empty/None disables the feature.
    servers_json: str | None = None
    # Path to a JSON file of AniSkip opening/ending intervals that the ani_skip Lua
    # polls after launch. Fetching AniSkip is kept OFF the launch path: mpv spawns
    # immediately with skip enabled (chapter fallback works at once) and the
    # intervals arrive via this file a moment later, well before the opening plays.
    skip_json: str | None = None
