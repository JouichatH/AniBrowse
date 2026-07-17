"""
MPV player integration for Ani-Browse.

This module provides the MpvPlayer class, which implements the BasePlayer interface for the MPV media player.
"""

import logging
import re
import shutil
import subprocess
import sys

from ....core.config import MpvConfig
from ....core.constants import SCRIPTS_DIR
from ....core.exceptions import AniBrowseError
from ....core.patterns import TORRENT_REGEX, YOUTUBE_REGEX
from ....core.utils import detect
from ..base import BasePlayer
from ..params import PlayerParams
from ..types import PlayerResult

logger = logging.getLogger(__name__)

ANI_SKIP_LUA = SCRIPTS_DIR / "mpv" / "ani_skip.lua"

MPV_AV_TIME_PATTERN = re.compile(r"[AV]+: ([0-9:]+) / ([0-9:]+) \(([0-9]+)%\)")


#: mpv exit codes emitted by ani_skip.lua's Shift+N / Shift+P bindings.
NEXT_EPISODE_EXIT_CODE = 100
PREVIOUS_EPISODE_EXIT_CODE = 101


def _ani_lua_args(params: PlayerParams) -> list[str]:
    """mpv args that load ani_skip.lua for in-player nav keys + op/ed skipping.

    Always loaded on the clean path (the nav keys need it); the skip options are
    passed through from ``params``. Returns ``[]`` only if the script is missing.
    """
    if not ANI_SKIP_LUA.exists():
        return []
    op = params.skip_op or (-1.0, -1.0)
    ed = params.skip_ed or (-1.0, -1.0)
    opts = (
        "ani_skip-nav_keys=yes,"
        f"ani_skip-op_enabled={'yes' if params.skip_op_enabled else 'no'},"
        f"ani_skip-ed_enabled={'yes' if params.skip_ed_enabled else 'no'},"
        f"ani_skip-op_start={op[0]},ani_skip-op_end={op[1]},"
        f"ani_skip-ed_start={ed[0]},ani_skip-ed_end={ed[1]}"
    )
    # In-player server switch: the Lua only binds Ctrl+S when given a servers
    # JSON path. Paths never contain commas (which separate script-opts), so this
    # is safe to append verbatim.
    if params.servers_json:
        opts += f",ani_skip-servers_json={params.servers_json}"
    # AniSkip intervals delivered via file (fetched off the launch path).
    if params.skip_json:
        opts += f",ani_skip-skip_json={params.skip_json}"
    return [f"--script={ANI_SKIP_LUA}", f"--script-opts={opts}"]


def _run_mpv_teed(args: list[str], env: dict) -> tuple[str, int | None]:
    """Run mpv, streaming its ``[viu-...]`` diagnostic lines to the terminal
    live while capturing the full output for post-playback parsing.

    Replaces a plain ``subprocess.run(capture_output=True)``: that hid mpv's
    output until after exit, so the opening/ending detection log was only ever
    visible in app.log. Here we still capture everything (for
    ``parse_playback_time`` and ``_log_mpv_chapters``) but echo the skip/chapter
    diagnostic lines as they arrive, so detection is watchable in action.

    stderr is merged into stdout so the single stream carries both mpv's log
    messages (where the Lua's ``print`` lands) and the status line.
    """
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
    )
    captured: list[str] = []
    assert proc.stdout is not None
    for chunk in iter(proc.stdout.readline, ""):
        captured.append(chunk)
        # mpv rewrites its status line in place with \r; split on it too so our
        # \n-terminated diagnostic lines are not hidden behind the status line.
        for piece in chunk.replace("\r", "\n").split("\n"):
            if "[ani-skip]" in piece or "[ani-chapters]" in piece:
                try:
                    sys.stderr.write(piece.strip() + "\n")
                    sys.stderr.flush()
                except (UnicodeError, OSError):
                    # Never let a terminal encoding/pipe hiccup kill playback;
                    # the line is still captured for app.log regardless.
                    pass
    proc.stdout.close()
    returncode = proc.wait()
    return "".join(captured), returncode


def _action_for_exit_code(code: int | None) -> str | None:
    if code == NEXT_EPISODE_EXIT_CODE:
        return "next"
    if code == PREVIOUS_EPISODE_EXIT_CODE:
        return "previous"
    return None


_CHAPTER_LINE = re.compile(
    r"\[ani-chapters\] #(\d+) t=(-?[0-9.]+) title=(.*)"
)


def parse_mpv_chapters(
    stdout: str | None, stderr: str | None
) -> list[tuple[float, str]]:
    """Extract the ``(time, title)`` chapters that ani_skip.lua logged.

    The embedded chapter list comes from the media container the source served;
    capturing the real titles lets us see the OP/ED naming variations and tune
    the Lua's chapter matcher against actual data.
    """
    chapters: list[tuple[float, str]] = []
    for stream in (stdout, stderr):
        if not stream:
            continue
        for line in stream.splitlines():
            m = _CHAPTER_LINE.search(line)
            if m:
                chapters.append((float(m.group(2)), m.group(3).strip()))
    return chapters


def _log_mpv_chapters(stdout: str | None, stderr: str | None) -> None:
    chapters = parse_mpv_chapters(stdout, stderr)
    if chapters:
        logger.info(
            "mpv chapters: %s",
            ", ".join(f"{t:.0f}s={title!r}" for t, title in chapters),
        )
    # Also surface any skips the ani_skip Lua performed, for diagnosing coverage.
    for stream in (stdout, stderr):
        if not stream:
            continue
        for line in stream.splitlines():
            i = line.find("[ani-skip]")
            if i != -1:
                logger.info("ani_skip %s", line[i + len("[ani-skip]"):].strip())


def parse_playback_time(
    stdout: str | None, stderr: str | None
) -> tuple[str | None, str | None]:
    """Extract the final ``(stop_time, total_time)`` from captured mpv output.

    mpv rewrites its ``AV: 00:10 / 24:00 (41%)`` status line in place using
    carriage returns, and depending on build/OS emits it on stdout or stderr, so
    we scan BOTH and split on \\r and \\n. Scanning in reverse yields the LAST
    reported position - i.e. where playback actually stopped - which is what auto
    -next needs to tell "watched to the end" from "quit early". Returns
    ``(None, None)`` if no status line was captured.
    """
    combined = f"{stdout or ''}\n{stderr or ''}"
    for line in reversed(re.split(r"[\r\n]+", combined)):
        match = MPV_AV_TIME_PATTERN.search(line.strip())
        if match:
            return match.group(1), match.group(2)
    return None, None


class MpvPlayer(BasePlayer):
    """
    MPV player implementation for Ani-Browse.

    Provides playback functionality using the MPV media player, supporting desktop, mobile, torrents, and syncplay.
    """

    def __init__(self, config: MpvConfig):
        """
        Initialize the MpvPlayer with the given MPV configuration.

        Args:
            config: MpvConfig object containing MPV-specific settings.
        """
        self.config = config
        self.executable = shutil.which("mpv")

    def play(self, params):
        """
        Play the given media using MPV, handling desktop, mobile, torrent, and syncplay scenarios.

        Args:
            params: PlayerParams object containing playback parameters.

        Returns:
            PlayerResult: Information about the playback session.
        """
        if TORRENT_REGEX.match(params.url) and detect.is_running_in_termux():
            raise AniBrowseError("Unable to play torrents on termux")
        elif params.syncplay and detect.is_running_in_termux():
            raise AniBrowseError("Unable to play with syncplay on termux")
        elif detect.is_running_in_termux():
            return self._play_on_mobile(params)
        else:
            return self._play_on_desktop(params)

    def _play_on_mobile(self, params) -> PlayerResult:
        """
        Play media on a mobile device using Android intents.

        Args:
            params: PlayerParams object containing playback parameters.

        Returns:
            PlayerResult: Information about the playback session.
        """
        if YOUTUBE_REGEX.match(params.url):
            args = [
                "nohup",
                "am",
                "start",
                "--user",
                "0",
                "-a",
                "android.intent.action.VIEW",
                "-d",
                params.url,
                "-n",
                "com.google.android.youtube/.UrlActivity",
            ]
        else:
            args = [
                "nohup",
                "am",
                "start",
                "--user",
                "0",
                "-a",
                "android.intent.action.VIEW",
                "-d",
                params.url,
                "-n",
                "is.xyz.mpv/.MPVActivity",
            ]

        subprocess.run(args,env=detect.get_clean_env())

        return PlayerResult(params.episode)

    def _play_on_desktop(self, params) -> PlayerResult:
        """
        Play media on a desktop environment using MPV.

        Args:
            params: PlayerParams object containing playback parameters.

        Returns:
            PlayerResult: Information about the playback session.
        """
        if not self.executable:
            raise AniBrowseError("MPV executable not found in PATH.")

        if TORRENT_REGEX.search(params.url):
            return self._stream_on_desktop_with_webtorrent_cli(params)
        elif params.syncplay:
            return self._stream_on_desktop_with_syncplay(params)
        else:
            return self._stream_on_desktop_with_subprocess(params)

    def _stream_on_desktop_with_subprocess(self, params: PlayerParams) -> PlayerResult:
        """
        Stream media using MPV via subprocess, capturing playback times.

        Args:
            params: PlayerParams object containing playback parameters.

        Returns:
            PlayerResult: Information about the playback session, including stop and total time.
        """
        mpv_args = [self.executable, params.url]

        mpv_args.extend(self._create_mpv_cli_options(params))
        # Load the ani_skip Lua for in-player next/prev keys and opening/ending
        # skip (the IPC path does its own thing, so this is clean-path only).
        mpv_args.extend(_ani_lua_args(params))

        pre_args = self.config.pre_args.split(",") if self.config.pre_args else []

        output, returncode = _run_mpv_teed(
            pre_args + mpv_args, detect.get_clean_env()
        )
        stop_time, total_time = parse_playback_time(output, None)
        # Record the episode's embedded chapters (from ani_skip.lua) so real
        # OP/ED title variations land in the log for tuning the skip matcher.
        _log_mpv_chapters(output, None)
        return PlayerResult(
            episode=params.episode,
            total_time=total_time,
            stop_time=stop_time,
            action=_action_for_exit_code(returncode),
        )

    def play_with_ipc(self, params: PlayerParams, socket_path: str) -> subprocess.Popen:
        """
        Stream using MPV with IPC (Inter-Process Communication) for enhanced features.

        Args:
            params: PlayerParams object containing playback parameters.
            socket_path: Path to the IPC socket for player control.

        Returns:
            subprocess.Popen: The running MPV process.
        """
        mpv_args = [
            self.executable,
            f"--input-ipc-server={socket_path}",
            "--idle=yes",
            "--force-window=yes",
            params.url,
        ]

        # Add custom MPV arguments
        mpv_args.extend(self._create_mpv_cli_options(params))

        # Add pre-args if configured
        pre_args = self.config.pre_args.split(",") if self.config.pre_args else []

        logger.info(f"Starting MPV with IPC socket: {socket_path}")

        process = subprocess.Popen(pre_args + mpv_args,env=detect.get_clean_env())

        return process

    def _stream_on_desktop_with_webtorrent_cli(
        self, params: PlayerParams
    ) -> PlayerResult:
        """
        Stream torrent media using the webtorrent CLI and MPV.

        Args:
            params: PlayerParams object containing playback parameters.

        Returns:
            PlayerResult: Information about the playback session.
        """
        WEBTORRENT_CLI = shutil.which("webtorrent")
        if not WEBTORRENT_CLI:
            raise AniBrowseError("Please Install webtorrent cli inorder to stream torrents")

        args = [WEBTORRENT_CLI, params.url, "--mpv"]
        if mpv_args := self._create_mpv_cli_options(params):
            args.append("--player-args")
            args.extend(mpv_args)

        subprocess.run(args,env=detect.get_clean_env())
        return PlayerResult(params.episode)

    def _stream_on_desktop_with_syncplay(self, params: PlayerParams) -> PlayerResult:
        """
        Stream media using Syncplay for synchronized playback with friends.

        Args:
            params: PlayerParams object containing playback parameters.

        Returns:
            PlayerResult: Information about the playback session.
        """
        SYNCPLAY_EXECUTABLE = shutil.which("syncplay")
        if not SYNCPLAY_EXECUTABLE:
            raise AniBrowseError(
                "Please install syncplay to be able to stream with your friends"
            )
        args = [SYNCPLAY_EXECUTABLE, params.url]
        if mpv_args := self._create_mpv_cli_options(params):
            args.append("--")
            args.extend(mpv_args)
        subprocess.run(args,env=detect.get_clean_env())

        return PlayerResult(params.episode)

    def _create_mpv_cli_options(self, params: PlayerParams) -> list[str]:
        """
        Create a list of MPV CLI options based on playback parameters.

        Args:
            params: PlayerParams object containing playback parameters.

        Returns:
            list[str]: List of MPV CLI arguments.
        """
        mpv_args = []
        if params.headers:
            header_str = ",".join([f"{k}:{v}" for k, v in params.headers.items()])
            mpv_args.append(f"--http-header-fields={header_str}")

        if params.subtitles:
            for sub in params.subtitles:
                mpv_args.append(f"--sub-file={sub}")

        if params.start_time:
            mpv_args.append(f"--start={params.start_time}")

        if params.title:
            mpv_args.append(f"--title={params.title}")

        if self.config.args:
            mpv_args.extend(self.config.args.split(","))
        return mpv_args


if __name__ == "__main__":
    from ....core.constants import APP_ASCII_ART

    print(APP_ASCII_ART)
    url = input("Enter the url you would like to stream: ")
    mpv = MpvPlayer(MpvConfig())
    player_result = mpv.play(PlayerParams(episode="", query="", url=url, title=""))
    print(player_result)
