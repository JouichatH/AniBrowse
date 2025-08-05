"""
Syncplay integration for FastAnime.

This module provides a procedural function to launch Syncplay with the given media and options.
"""

import shutil
import subprocess

from .tools import exit_app


def SyncPlayer(url: str, anime_title=None, headers={}, subtitles=[], *args):
    """
    Launch Syncplay for synchronized playback with friends.

    Args:
        url: The media URL to play.
        anime_title: Optional title to display in the player.
        headers: Optional HTTP headers to pass to the player.
        subtitles: Optional list of subtitle dicts with 'url' keys.
        *args: Additional arguments (unused).

    Returns:
        Tuple of ("0", "0") for compatibility.
    """
    # TODO: handle m3u8 multi quality streams
    #
    # check for SyncPlay
    SYNCPLAY_EXECUTABLE = shutil.which("syncplay")
    if not SYNCPLAY_EXECUTABLE:
        print("Syncplay not found")
        exit_app(1)
        return "0", "0"
    # start SyncPlayer
    mpv_args = []
    if headers:
        mpv_headers = "--http-header-fields="
        for header_name, header_value in headers.items():
            mpv_headers += f"{header_name}:{header_value},"
        mpv_args.append(mpv_headers)
    for subtitle in subtitles:
        mpv_args.append(f"--sub-file={subtitle['url']}")
    if not anime_title:
        subprocess.run(
            [
                SYNCPLAY_EXECUTABLE,
                url,
            ],
            check=False,
        )
    else:
        subprocess.run(
            [
                SYNCPLAY_EXECUTABLE,
                url,
                "--",
                f"--force-media-title={anime_title}",
                *mpv_args,
            ],
            check=False,
        )

    # for compatability
    return "0", "0"
