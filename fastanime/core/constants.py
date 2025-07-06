import os
from importlib import resources

APP_NAME = os.environ.get("FASTANIME_APP_NAME", "fastanime")

try:
    pkg = resources.files("fastanime")

    ASSETS_DIR = pkg / "assets"
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

    pkg = Path(__file__).resolve().parent.parent
    ASSETS_DIR = pkg / "assets"
    DEFAULTS = ASSETS_DIR / "defaults"
    ICONS_DIR = ASSETS_DIR / "icons"

    # rofi files
    ROFI_THEME_MAIN = DEFAULTS / "rofi" / "main.rasi"
    ROFI_THEME_INPUT = DEFAULTS / "rofi" / "input.rasi"
    ROFI_THEME_CONFIRM = DEFAULTS / "rofi" / "confirm.rasi"
    ROFI_THEME_PREVIEW = DEFAULTS / "rofi" / "preview.rasi"

    # fzf
    FZF_DEFAULT_OPTS = DEFAULTS / "fzf-opts"
