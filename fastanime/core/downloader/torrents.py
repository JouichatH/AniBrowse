import shutil
import subprocess
from pathlib import Path

from ..exceptions import FastAnimeError


def download_torrent_with_webtorrent_cli(path: Path, url: str) -> Path:
    """Download torrent using webtorrent CLI and return the download path."""
    WEBTORRENT_CLI = shutil.which("webtorrent")
    if not WEBTORRENT_CLI:
        raise FastAnimeError("Please install webtorrent cli inorder to download torrents")
    cmd = [WEBTORRENT_CLI, "download", url, "--out", str(path.parent)]
    subprocess.run(cmd, check=False)
    return path
