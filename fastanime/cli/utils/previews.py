import concurrent.futures
import logging
import textwrap
from hashlib import sha256
from io import StringIO
from pathlib import Path
from threading import Thread
from typing import TYPE_CHECKING, List

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ...core.config import AppConfig
from ...core.constants import APP_DIR, PLATFORM
from .scripts import bash_functions

if TYPE_CHECKING:
    from ...libs.api.types import MediaItem

logger = logging.getLogger(__name__)

# --- Constants for Paths ---
PREVIEWS_CACHE_DIR = APP_CACHE_DIR / "previews"
IMAGES_CACHE_DIR = PREVIEWS_CACHE_DIR / "images"
INFO_CACHE_DIR = PREVIEWS_CACHE_DIR / "info"
FZF_SCRIPTS_DIR = APP_DIR / "libs" / "selectors" / "fzf" / "scripts"
PREVIEW_SCRIPT_TEMPLATE_PATH = FZF_SCRIPTS_DIR / "preview.sh"

# Ensure cache directories exist on startup
IMAGES_CACHE_DIR.mkdir(parents=True, exist_ok=True)
INFO_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# The helper functions (_get_cache_hash, _save_image_from_url, _save_info_text,
# _format_info_text, and _cache_worker) remain exactly the same as before.
# I am including them here for completeness.


def _get_cache_hash(text: str) -> str:
    """Generates a consistent SHA256 hash for a given string to use as a filename."""
    return sha256(text.encode("utf-8")).hexdigest()


def _save_image_from_url(url: str, hash_id: str):
    """Downloads an image using httpx and saves it to the cache."""
    try:
        temp_image_path = IMAGES_CACHE_DIR / f"{hash_id}.png.tmp"
        image_path = IMAGES_CACHE_DIR / f"{hash_id}.png"
        with httpx.stream("GET", url, follow_redirects=True, timeout=20) as response:
            response.raise_for_status()
            with temp_image_path.open("wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
        temp_image_path.rename(image_path)
    except Exception as e:
        logger.error(f"Failed to download image {url}: {e}")
        if temp_image_path.exists():
            temp_image_path.unlink()


def _save_info_text(info_text: str, hash_id: str):
    """Saves pre-formatted text to the info cache."""
    try:
        info_path = INFO_CACHE_DIR / hash_id
        info_path.write_text(info_text, encoding="utf-8")
    except IOError as e:
        logger.error(f"Failed to write info cache for {hash_id}: {e}")


def _format_info_text(item: MediaItem) -> str:
    """Uses Rich to format a media item's details into a string."""
    from .anilist import anilist_data_helper

    io_buffer = StringIO()
    console = Console(file=io_buffer, force_terminal=True, color_system="truecolor")
    title = Text(
        item.title.english or item.title.romaji or "Unknown Title", style="bold cyan"
    )
    description = anilist_data_helper.clean_html(
        item.description or "No description available."
    )
    description = (description[:350] + "...") if len(description) > 350 else description
    genres = f"[bold]Genres:[/bold] {', '.join(item.genres)}"
    status = f"[bold]Status:[/bold] {item.status}"
    score = f"[bold]Score:[/bold] {item.average_score / 10 if item.average_score else 'N/A'}"
    panel_content = f"{genres}\n{status}\n{score}\n\n{description}"
    console.print(Panel(panel_content, title=title, border_style="dim"))
    return io_buffer.getvalue()


def _cache_worker(items: List[MediaItem], titles: List[str], config: AppConfig):
    """The background task that fetches and saves all necessary preview data."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for item, title_str in zip(items, titles):
            hash_id = _get_cache_hash(title_str)
            if config.general.preview in ("full", "image") and item.cover_image:
                if not (IMAGES_CACHE_DIR / f"{hash_id}.png").exists():
                    executor.submit(
                        _save_image_from_url, item.cover_image.large, hash_id
                    )
            if config.general.preview in ("full", "text"):
                if not (INFO_CACHE_DIR / hash_id).exists():
                    info_text = _format_info_text(item)
                    executor.submit(_save_info_text, info_text, hash_id)


# --- THIS IS THE MODIFIED FUNCTION ---
def get_anime_preview(
    items: List[MediaItem], titles: List[str], config: AppConfig
) -> str:
    """
    Starts a background task to cache preview data and returns the fzf preview command
    by formatting a shell script template.
    """
    # Start the non-blocking background Caching
    Thread(target=_cache_worker, args=(items, titles, config), daemon=True).start()

    # Read the shell script template from the file system.
    try:
        template = PREVIEW_SCRIPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error(
            f"Preview script template not found at {PREVIEW_SCRIPT_TEMPLATE_PATH}"
        )
        return "echo 'Error: Preview script template not found.'"

    # Prepare values to inject into the template
    path_sep = "\\" if PLATFORM == "win32" else "/"

    # Format the template with the dynamic values
    final_script = template.format(
        bash_functions=bash_functions,
        preview_mode=config.general.preview,
        image_cache_path=str(IMAGES_CACHE_DIR),
        info_cache_path=str(INFO_CACHE_DIR),
        path_sep=path_sep,
    )

    # Return the command for fzf to execute. `sh -c` is used to run the script string.
    # The -- "{}" ensures that the selected item is passed as the first argument ($1)
    # to the script, even if it contains spaces or special characters.
    return f'sh -c {final_script!r} -- "{{}}"'
