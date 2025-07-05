import os
import sys
from pathlib import Path
from platform import system

import click

from ..core.constants import APP_NAME, ICONS_DIR

ASCII_ART = """

███████╗░█████╗░░██████╗████████╗░█████╗░███╗░░██╗██╗███╗░░░███╗███████╗
██╔════╝██╔══██╗██╔════╝╚══██╔══╝██╔══██╗████╗░██║██║████╗░████║██╔════╝
█████╗░░███████║╚█████╗░░░░██║░░░███████║██╔██╗██║██║██╔████╔██║█████╗░░
██╔══╝░░██╔══██║░╚═══██╗░░░██║░░░██╔══██║██║╚████║██║██║╚██╔╝██║██╔══╝░░
██║░░░░░██║░░██║██████╔╝░░░██║░░░██║░░██║██║░╚███║██║██║░╚═╝░██║███████╗
╚═╝░░░░░╚═╝░░╚═╝╚═════╝░░░░╚═╝░░░╚═╝░░╚═╝╚═╝░░╚══╝╚═╝╚═╝░░░░░╚═╝╚══════╝

"""
PLATFORM = system()
USER_NAME = os.environ.get("USERNAME", "Anime Fan")


APP_DATA_DIR = Path(click.get_app_dir(APP_NAME, roaming=False))

if sys.platform == "win32":
    APP_CACHE_DIR = APP_DATA_DIR / "cache"
    USER_VIDEOS_DIR = Path.home() / "Videos" / APP_NAME

elif sys.platform == "darwin":
    APP_CACHE_DIR = Path.home() / "Library" / "Caches" / APP_NAME
    USER_VIDEOS_DIR = Path.home() / "Movies" / APP_NAME

else:
    xdg_cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    APP_CACHE_DIR = xdg_cache_home / APP_NAME

    xdg_videos_dir = Path(os.environ.get("XDG_VIDEOS_DIR", Path.home() / "Videos"))
    USER_VIDEOS_DIR = xdg_videos_dir / APP_NAME

APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
APP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
USER_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

USER_DATA_PATH = APP_DATA_DIR / "user_data.json"
USER_WATCH_HISTORY_PATH = APP_DATA_DIR / "watch_history.json"
USER_CONFIG_PATH = APP_DATA_DIR / "config.ini"
LOG_FILE_PATH = APP_CACHE_DIR / "fastanime.log"

ICON_PATH = ICONS_DIR / ("logo.ico" if PLATFORM == "Windows" else "logo.png")
