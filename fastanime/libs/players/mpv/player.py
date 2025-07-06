import logging
import re
import shutil
import subprocess

from ....core.config import MpvConfig
from ..base import BasePlayer, PlayerResult

logger = logging.getLogger(__name__)

MPV_AV_TIME_PATTERN = re.compile(r"AV: ([0-9:]*) / ([0-9:]*) \(([0-9]*)%\)")


class MpvPlayer(BasePlayer):
    def __init__(self, config: MpvConfig):
        self.config = config
        self.executable = shutil.which("mpv")

    def play(self, url, title, subtitles=None, headers=None, start_time="0"):
        if not self.executable:
            raise FileNotFoundError("MPV executable not found in PATH.")

        mpv_args = []
        if headers:
            header_str = ",".join([f"{k}:{v}" for k, v in headers.items()])
            mpv_args.append(f"--http-header-fields={header_str}")

        if subtitles:
            for sub in subtitles:
                mpv_args.append(f"--sub-file={sub.url}")

        if start_time != "0":
            mpv_args.append(f"--start={start_time}")

        if title:
            mpv_args.append(f"--title={title}")

        if self.config.args:
            mpv_args.extend(self.config.args.split(","))

        pre_args = self.config.pre_args.split(",") if self.config.pre_args else []

        if self.config.use_python_mpv:
            self._stream_with_python_mpv()
        else:
            self._stream_with_subprocess(self.executable, url, [], pre_args)
        return PlayerResult()

    def _stream_with_subprocess(self, mpv_executable, url, mpv_args, pre_args):
        last_time = "0"
        total_time = "0"

        proc = subprocess.run(
            pre_args + [mpv_executable, url, *mpv_args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if proc.stdout:
            for line in reversed(proc.stdout.split("\n")):
                match = MPV_AV_TIME_PATTERN.search(line.strip())
                if match:
                    last_time = match.group(1)
                    total_time = match.group(2)
                    break
        return last_time, total_time

    def _stream_with_python_mpv(self):
        return "0", "0"
