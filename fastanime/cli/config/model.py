import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ...core.constants import (
    FZF_DEFAULT_OPTS,
    ROFI_THEME_CONFIRM,
    ROFI_THEME_INPUT,
    ROFI_THEME_MAIN,
    ROFI_THEME_PREVIEW,
)
from ...libs.anilist.constants import SORTS_AVAILABLE
from ...libs.anime_provider import PROVIDERS_AVAILABLE, SERVERS_AVAILABLE
from ..constants import APP_ASCII_ART, USER_VIDEOS_DIR


class External(BaseModel):
    pass


class FzfConfig(External):
    """Configuration specific to the FZF selector."""

    opts: str = Field(
        default_factory=lambda: "\n"
        + "\n".join(
            [
                f"\t{line}"
                for line in FZF_DEFAULT_OPTS.read_text(encoding="utf-8").split()
            ]
        ),
        description="Command-line options to pass to FZF for theming and behavior.",
    )
    header_color: str = Field(
        default="95,135,175", description="RGB color for the main TUI header."
    )
    header_ascii_art: str = Field(
        default="\n" + "\n".join([f"\t{line}" for line in APP_ASCII_ART.split("\n")]),
        description="The ASCII art to display in TUI headers.",
    )
    preview_header_color: str = Field(
        default="215,0,95", description="RGB color for preview pane headers."
    )
    preview_separator_color: str = Field(
        default="208,208,208", description="RGB color for preview pane separators."
    )


class RofiConfig(External):
    """Configuration specific to the Rofi selector."""

    theme_main: Path = Field(
        default=Path(str(ROFI_THEME_MAIN)),
        description="Path to the main Rofi theme file.",
    )
    theme_preview: Path = Field(
        default=Path(str(ROFI_THEME_PREVIEW)),
        description="Path to the Rofi theme file for previews.",
    )
    theme_confirm: Path = Field(
        default=Path(str(ROFI_THEME_CONFIRM)),
        description="Path to the Rofi theme file for confirmation prompts.",
    )
    theme_input: Path = Field(
        default=Path(str(ROFI_THEME_INPUT)),
        description="Path to the Rofi theme file for user input prompts.",
    )


class MpvConfig(External):
    """Configuration specific to the MPV player integration."""

    args: str = Field(
        default="", description="Comma-separated arguments to pass to the MPV player."
    )
    pre_args: str = Field(
        default="",
        description="Comma-separated arguments to prepend before the MPV command.",
    )
    disable_popen: bool = Field(
        default=True,
        description="Disable using subprocess.Popen for MPV, which can be unstable on some systems.",
    )
    force_window: str = Field(
        default="immediate", description="Value for MPV's --force-window option."
    )
    use_python_mpv: bool = Field(
        default=False,
        description="Use the python-mpv library for enhanced player control.",
    )


class AnilistConfig(External):
    """Configuration for interacting with the AniList API."""

    per_page: int = Field(
        default=15,
        gt=0,
        le=50,
        description="Number of items to fetch per page from AniList.",
    )
    sort_by: str = Field(
        default="SEARCH_MATCH",
        description="Default sort order for AniList search results.",
        examples=SORTS_AVAILABLE,
    )
    preferred_language: Literal["english", "romaji"] = Field(
        default="english",
        description="Preferred language for anime titles from AniList.",
    )

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v: str) -> str:
        if v not in SORTS_AVAILABLE:
            raise ValueError(
                f"'{v}' is not a valid sort option. See documentation for available options."
            )
        return v


class GeneralConfig(BaseModel):
    """Configuration for general application behavior and integrations."""

    provider: str = Field(
        default="allanime",
        description="The default anime provider to use for scraping.",
        examples=list(PROVIDERS_AVAILABLE.keys()),
    )
    selector: Literal["default", "fzf", "rofi"] = Field(
        default="default", description="The interactive selector tool to use for menus."
    )
    auto_select_anime_result: bool = Field(
        default=True,
        description="Automatically select the best-matching search result from a provider.",
    )
    icons: bool = Field(
        default=False, description="Display emoji icons in the user interface."
    )
    preview: Literal["full", "text", "image", "none"] = Field(
        default="none", description="Type of preview to display in selectors."
    )
    image_renderer: Literal["icat", "chafa", "imgcat"] = Field(
        default="icat" if os.environ.get("KITTY_WINDOW_ID") else "chafa",
        description="The command-line tool to use for rendering images in the terminal.",
    )
    manga_viewer: Literal["feh", "icat"] = Field(
        default="feh",
        description="The external application to use for viewing manga pages.",
    )
    downloads_dir: Path = Field(
        default_factory=lambda: USER_VIDEOS_DIR,
        description="The default directory to save downloaded anime.",
    )
    check_for_updates: bool = Field(
        default=True,
        description="Automatically check for new versions of FastAnime on startup.",
    )
    cache_requests: bool = Field(
        default=True,
        description="Enable caching of network requests to speed up subsequent operations.",
    )
    max_cache_lifetime: str = Field(
        default="03:00:00",
        description="Maximum lifetime for a cached request in DD:HH:MM format.",
    )
    normalize_titles: bool = Field(
        default=True,
        description="Attempt to normalize provider titles to match AniList titles.",
    )
    discord: bool = Field(
        default=False,
        description="Enable Discord Rich Presence to show your current activity.",
    )
    recent: int = Field(
        default=50,
        ge=0,
        description="Number of recently watched anime to keep in history.",
    )

    @field_validator("provider")
    @classmethod
    def validate_server(cls, v: str) -> str:
        if v.lower() != "top" and v not in PROVIDERS_AVAILABLE:
            raise ValueError(
                f"'{v}' is not a valid server. Must be 'top' or one of: {PROVIDERS_AVAILABLE}"
            )
        return v


class StreamConfig(BaseModel):
    """Configuration specific to video streaming and playback."""

    player: Literal["mpv", "vlc"] = Field(
        default="mpv", description="The media player to use for streaming."
    )
    quality: Literal["360", "480", "720", "1080"] = Field(
        default="1080", description="Preferred stream quality."
    )
    translation_type: Literal["sub", "dub"] = Field(
        default="sub", description="Preferred audio/subtitle language type."
    )
    server: str = Field(
        default="top",
        description="The default server to use from a provider. 'top' uses the first available.",
        examples=SERVERS_AVAILABLE,
    )
    auto_next: bool = Field(
        default=False,
        description="Automatically play the next episode when the current one finishes.",
    )
    continue_from_watch_history: bool = Field(
        default=True,
        description="Automatically resume playback from the last known episode and position.",
    )
    preferred_watch_history: Literal["local", "remote"] = Field(
        default="local",
        description="Which watch history to prioritize: local file or remote AniList progress.",
    )
    auto_skip: bool = Field(
        default=False,
        description="Automatically skip openings/endings if skip data is available.",
    )
    episode_complete_at: int = Field(
        default=80,
        ge=0,
        le=100,
        description="Percentage of an episode to watch before it's marked as complete.",
    )
    ytdlp_format: str = Field(
        default="best[height<=1080]/bestvideo[height<=1080]+bestaudio/best",
        description="The format selection string for yt-dlp.",
    )
    force_forward_tracking: bool = Field(
        default=True,
        description="Prevent updating AniList progress to a lower episode number.",
    )
    default_media_list_tracking: Literal["track", "disabled", "prompt"] = Field(
        default="prompt",
        description="Default behavior for tracking progress on AniList.",
    )
    sub_lang: str = Field(
        default="eng",
        description="Preferred language code for subtitles (e.g., 'en', 'es').",
    )

    @field_validator("server")
    @classmethod
    def validate_server(cls, v: str) -> str:
        if v.lower() != "top" and v not in SERVERS_AVAILABLE:
            raise ValueError(
                f"'{v}' is not a valid server. Must be 'top' or one of: {SERVERS_AVAILABLE}"
            )
        return v


class AppConfig(BaseModel):
    """The root configuration model for the FastAnime application."""

    general: GeneralConfig = Field(
        default_factory=GeneralConfig,
        description="General configuration settings for application behavior.",
    )
    stream: StreamConfig = Field(
        default_factory=StreamConfig,
        description="Settings related to video streaming and playback.",
    )
    anilist: AnilistConfig = Field(
        default_factory=AnilistConfig,
        description="Configuration for AniList API integration.",
    )

    fzf: FzfConfig = Field(
        default_factory=FzfConfig,
        description="Settings for the FZF selector interface.",
    )
    rofi: RofiConfig = Field(
        default_factory=RofiConfig,
        description="Settings for the Rofi selector interface.",
    )
    mpv: MpvConfig = Field(
        default_factory=MpvConfig, description="Configuration for the MPV media player."
    )
