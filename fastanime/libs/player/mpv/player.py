import logging
import re
import shutil
import subprocess

from ....core.config import MpvConfig
from ....core.exceptions import FastAnimeError
from ....core.patterns import TORRENT_REGEX, YOUTUBE_REGEX
from ....core.utils import detect
from ..base import BasePlayer
from ..params import PlayerParams
from ..types import PlayerResult

logger = logging.getLogger(__name__)

MPV_AV_TIME_PATTERN = re.compile(r"AV: ([0-9:]*) / ([0-9:]*) \(([0-9]*)%\)")


class MpvPlayer(BasePlayer):
    def __init__(self, config: MpvConfig):
        self.config = config
        self.executable = shutil.which("mpv")

    def play(self, params):
        if TORRENT_REGEX.match(params.url) and detect.is_running_in_termux():
            raise FastAnimeError("Unable to play torrents on termux")
        elif params.syncplay and detect.is_running_in_termux():
            raise FastAnimeError("Unable to play torrents on termux")
        elif detect.is_running_in_termux():
            return self._play_on_mobile(params)
        else:
            return self._play_on_desktop(params)

    def _play_on_mobile(self, params) -> PlayerResult:
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

        subprocess.run(args)

        return PlayerResult(params.episode)

    def _play_on_desktop(self, params) -> PlayerResult:
        if not self.executable:
            raise FastAnimeError("MPV executable not found in PATH.")

        if TORRENT_REGEX.search(params.url):
            return self._stream_on_desktop_with_webtorrent_cli(params)
        elif params.syncplay:
            return self._stream_on_desktop_with_syncplay(params)
        else:
            return self._stream_on_desktop_with_subprocess(params)

    def _stream_on_desktop_with_subprocess(self, params: PlayerParams) -> PlayerResult:
        mpv_args = [self.executable, params.url]

        mpv_args.extend(self._create_mpv_cli_options(params))

        pre_args = self.config.pre_args.split(",") if self.config.pre_args else []

        stop_time = None
        total_time = None

        proc = subprocess.run(
            pre_args + mpv_args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if proc.stdout:
            for line in reversed(proc.stdout.split("\n")):
                match = MPV_AV_TIME_PATTERN.search(line.strip())
                if match:
                    stop_time = match.group(1)
                    total_time = match.group(2)
                    break
        return PlayerResult(
            episode=params.episode, total_time=total_time, stop_time=stop_time
        )

    def play_with_ipc(self, params: PlayerParams, socket_path: str) -> subprocess.Popen:
        """Stream using IPC player for enhanced features."""
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

        process = subprocess.Popen(pre_args + mpv_args)

        return process

    def _stream_on_desktop_with_webtorrent_cli(
        self, params: PlayerParams
    ) -> PlayerResult:
        WEBTORRENT_CLI = shutil.which("webtorrent")
        if not WEBTORRENT_CLI:
            raise FastAnimeError(
                "Please Install webtorrent cli inorder to stream torrents"
            )

        args = [WEBTORRENT_CLI, params.url, "--mpv"]
        if mpv_args := self._create_mpv_cli_options(params):
            args.append("--player-args")
            args.extend(mpv_args)

        subprocess.run(args)
        return PlayerResult(params.episode)

    # TODO: Get people with real friends to do this lol
    def _stream_on_desktop_with_syncplay(self, params: PlayerParams) -> PlayerResult:
        SYNCPLAY_EXECUTABLE = shutil.which("syncplay")
        if not SYNCPLAY_EXECUTABLE:
            raise FastAnimeError(
                "Please install syncplay to be able to stream with your friends"
            )
        args = [SYNCPLAY_EXECUTABLE, params.url]
        if mpv_args := self._create_mpv_cli_options(params):
            args.append("--")
            args.extend(mpv_args)
        subprocess.run(args)

        return PlayerResult(params.episode)

    def _create_mpv_cli_options(self, params: PlayerParams) -> list[str]:
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
