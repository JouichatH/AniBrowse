import shutil
import subprocess
from pathlib import Path

from ..exceptions import FastAnimeError


def download_torrent_with_webtorrent_cli(path: Path, url: str):
    WEBTORRENT_CLI = shutil.which("webtorrent")
    if not WEBTORRENT_CLI:
        FastAnimeError("Please install webtorrent cli inorder to download torrents")
    cmd = [WEBTORRENT_CLI, "download", url, "--out", path]
    subprocess.run(cmd, check=False)
    return
