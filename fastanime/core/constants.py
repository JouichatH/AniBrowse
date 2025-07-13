import os
import sys
from importlib import resources
from pathlib import Path

PLATFORM = sys.platform
APP_NAME = os.environ.get("FASTANIME_APP_NAME", "fastanime")
PROJECT_NAME = "FASTANIME"

try:
    APP_DIR = Path(str(resources.files("fastanime")))

    ASSETS_DIR = APP_DIR / "assets"
    DEFAULTS = ASSETS_DIR / "defaults"
    ICONS_DIR = ASSETS_DIR / "icons"

    # rofi files
    ROFI_THEME_MAIN = DEFAULTS / "rofi" / "main.rasi"
    ROFI_THEME_INPUT = DEFAULTS / "rofi" / "input.rasi"
    ROFI_THEME_CONFIRM = DEFAULTS / "rofi" / "confirm.rasi"
    ROFI_THEME_PREVIEW = DEFAULTS / "rofi" / "preview.rasi"

    # fzf
    FZF_DEFAULT_OPTS = DEFAULTS / "fzf-opts"


except ModuleNotFoundError:
    from pathlib import Path

    APP_DIR = Path(__file__).resolve().parent.parent
    ASSETS_DIR = APP_DIR / "assets"
    DEFAULTS = ASSETS_DIR / "defaults"
    ICONS_DIR = ASSETS_DIR / "icons"

    # rofi files
    ROFI_THEME_MAIN = DEFAULTS / "rofi" / "main.rasi"
    ROFI_THEME_INPUT = DEFAULTS / "rofi" / "input.rasi"
    ROFI_THEME_CONFIRM = DEFAULTS / "rofi" / "confirm.rasi"
    ROFI_THEME_PREVIEW = DEFAULTS / "rofi" / "preview.rasi"

    # fzf
    FZF_DEFAULT_OPTS = DEFAULTS / "fzf-opts"


USER_NAME = os.environ.get("USERNAME", "Anime Fan")

try:
    import click

    APP_DATA_DIR = Path(click.get_app_dir(APP_NAME, roaming=False))
except ModuleNotFoundError:
    if PLATFORM == "win32":
        folder = os.environ.get("LOCALAPPDATA")
        if folder is None:
            folder = Path.home()
        APP_DATA_DIR = Path(folder) / APP_NAME
    if PLATFORM == "darwin":
        APP_DATA_DIR = Path(Path.home() / "Library" / "Application Support" / APP_NAME)

    APP_DATA_DIR = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME
    )

if PLATFORM == "win32":
    APP_CACHE_DIR = APP_DATA_DIR / "cache"
    USER_VIDEOS_DIR = Path.home() / "Videos" / APP_NAME

elif PLATFORM == "darwin":
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

ICON_PATH = ICONS_DIR / ("logo.ico" if PLATFORM == "Win32" else "logo.png")


APP_ASCII_ART = """\
███████╗░█████╗░░██████╗████████╗░█████╗░███╗░░██╗██╗███╗░░░███╗███████╗
██╔════╝██╔══██╗██╔════╝╚══██╔══╝██╔══██╗████╗░██║██║████╗░████║██╔════╝
█████╗░░███████║╚█████╗░░░░██║░░░███████║██╔██╗██║██║██╔████╔██║█████╗░░
██╔══╝░░██╔══██║░╚═══██╗░░░██║░░░██╔══██║██║╚████║██║██║╚██╔╝██║██╔══╝░░
██║░░░░░██║░░██║██████╔╝░░░██║░░░██║░░██║██║░╚███║██║██║░╚═╝░██║███████╗
╚═╝░░░░░╚═╝░░╚═╝╚═════╝░░░░╚═╝░░░╚═╝░░╚═╝╚═╝░░╚══╝╚═╝╚═╝░░░░░╚═╝╚══════╝
"""
