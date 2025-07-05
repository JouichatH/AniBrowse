from pathlib import Path
from typing import List, Literal
from pydantic import BaseModel, Field, ValidationError, field_validator, ConfigDict
from ..constants import USER_VIDEOS_DIR, ASCII_ART
from ...core.constants import (
    FZF_DEFAULT_OPTS,
    ROFI_THEME_MAIN,
    ROFI_THEME_INPUT,
    ROFI_THEME_CONFIRM,
    ROFI_THEME_PREVIEW,
)
from ...libs.anime_provider import SERVERS_AVAILABLE
from ...libs.anilist.constants import SORTS_AVAILABLE


class FzfConfig(BaseModel):
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
    header_color: str = "95,135,175"
    preview_header_color: str = "215,0,95"
    preview_separator_color: str = "208,208,208"


class RofiConfig(BaseModel):
    """Configuration specific to the Rofi selector."""

    theme_main: Path = Path(str(ROFI_THEME_MAIN))
    theme_preview: Path = Path(str(ROFI_THEME_PREVIEW))
    theme_confirm: Path = Path(str(ROFI_THEME_CONFIRM))
    theme_input: Path = Path(str(ROFI_THEME_INPUT))


class MpvConfig(BaseModel):
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


class GeneralConfig(BaseModel):
    """Configuration for general application behavior and integrations."""

    provider: Literal["allanime", "animepahe", "hianime", "nyaa", "yugen"] = "allanime"
    selector: Literal["default", "fzf", "rofi"] = "default"
    auto_select_anime_result: bool = True

    # UI/UX Settings
    icons: bool = False
    preview: Literal["full", "text", "image", "none"] = "none"
    image_renderer: Literal["icat", "chafa", "imgcat"] = "chafa"
    preferred_language: Literal["english", "romaji"] = "english"
    sub_lang: str = "eng"
    manga_viewer: Literal["feh", "icat"] = "feh"

    # Paths & Files
    downloads_dir: Path = USER_VIDEOS_DIR

    # Theming & Appearance
    header_ascii_art: str = Field(
        default="\n" + "\n".join([f"\t{line}" for line in ASCII_ART.split()]),
        description="ASCII art for TUI headers.",
    )

    # Advanced / Developer
    check_for_updates: bool = True
    cache_requests: bool = True
    max_cache_lifetime: str = "03:00:00"
    normalize_titles: bool = True
    discord: bool = False


class StreamConfig(BaseModel):
    """Configuration specific to video streaming and playback."""

    player: Literal["mpv", "vlc"] = "mpv"
    quality: Literal["360", "480", "720", "1080"] = "1080"
    translation_type: Literal["sub", "dub"] = "sub"

    server: str = "top"

    # Playback Behavior
    auto_next: bool = False
    continue_from_watch_history: bool = True
    preferred_watch_history: Literal["local", "remote"] = "local"
    auto_skip: bool = False
    episode_complete_at: int = Field(default=80, ge=0, le=100)

    # Technical/Downloader Settings
    ytdlp_format: str = "best[height<=1080]/bestvideo[height<=1080]+bestaudio/best"

    @field_validator("server")
    @classmethod
    def validate_server(cls, v: str) -> str:
        if v not in SERVERS_AVAILABLE:
            raise ValidationError(f"server must be one of {SERVERS_AVAILABLE}")
        return v


class AnilistConfig(BaseModel):
    """Configuration for interacting with the AniList API."""

    per_page: int = Field(default=15, gt=0, le=50)
    sort_by: str = "SEARCH_MATCH"
    default_media_list_tracking: Literal["track", "disabled", "prompt"] = "prompt"
    force_forward_tracking: bool = True
    recent: int = Field(default=50, ge=0)

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v: str) -> str:
        if v not in SORTS_AVAILABLE:
            raise ValidationError(f"sort_by must be one of {SORTS_AVAILABLE}")
        return v


class AppConfig(BaseModel):
    """The root configuration model for the FastAnime application."""

    general: GeneralConfig = Field(default_factory=GeneralConfig)
    stream: StreamConfig = Field(default_factory=StreamConfig)
    anilist: AnilistConfig = Field(default_factory=AnilistConfig)

    # Nested Tool-Specific Configs
    fzf: FzfConfig = Field(default_factory=FzfConfig)
    rofi: RofiConfig = Field(default_factory=RofiConfig)
    mpv: MpvConfig = Field(default_factory=MpvConfig)
