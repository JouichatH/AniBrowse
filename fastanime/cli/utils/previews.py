import concurrent.futures
import logging
import os
from hashlib import sha256
from threading import Thread
from typing import List

import httpx

from ...core.config import AppConfig
from ...core.constants import APP_CACHE_DIR, APP_DIR, PLATFORM
from ...core.utils.file import AtomicWriter
from ...libs.api.types import MediaItem
from . import ansi, formatters

logger = logging.getLogger(__name__)

# --- Constants for Paths ---
PREVIEWS_CACHE_DIR = APP_CACHE_DIR / "previews"
IMAGES_CACHE_DIR = PREVIEWS_CACHE_DIR / "images"
INFO_CACHE_DIR = PREVIEWS_CACHE_DIR / "info"
FZF_SCRIPTS_DIR = APP_DIR / "libs" / "selectors" / "fzf" / "scripts"
PREVIEW_SCRIPT_TEMPLATE_PATH = FZF_SCRIPTS_DIR / "preview.sh"
INFO_SCRIPT_TEMPLATE_PATH = FZF_SCRIPTS_DIR / "info.sh"
EPISODE_INFO_SCRIPT_TEMPLATE_PATH = FZF_SCRIPTS_DIR / "episode_info.sh"


def _get_cache_hash(text: str) -> str:
    """Generates a consistent SHA256 hash for a given string to use as a filename."""
    return sha256(text.encode("utf-8")).hexdigest()


def _save_image_from_url(url: str, hash_id: str):
    """Downloads an image using httpx and saves it to the cache."""
    image_path = IMAGES_CACHE_DIR / f"{hash_id}.png"
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=20) as response:
            response.raise_for_status()
            with AtomicWriter(image_path, "wb", encoding=None) as f:
                chunks = b""
                for chunk in response.iter_bytes():
                    chunks += chunk
                f.write(chunks)
    except Exception as e:
        logger.error(f"Failed to download image {url}: {e}")


def _save_info_text(info_text: str, hash_id: str):
    """Saves pre-formatted text to the info cache."""
    try:
        info_path = INFO_CACHE_DIR / hash_id
        with AtomicWriter(info_path) as f:
            f.write(info_text)
    except IOError as e:
        logger.error(f"Failed to write info cache for {hash_id}: {e}")


def _populate_info_template(item: MediaItem, config: AppConfig) -> str:
    """
    Takes the info.sh template and injects formatted, shell-safe data.
    """
    template = INFO_SCRIPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    description = formatters.clean_html(item.description or "No description available.")

    HEADER_COLOR = config.fzf.preview_header_color.split(",")
    SEPARATOR_COLOR = config.fzf.preview_separator_color.split(",")

    # Escape all variables before injecting them into the script
    replacements = {
        #
        # plain text
        #
        "TITLE": formatters.shell_safe(item.title.english or item.title.romaji),
        "STATUS": formatters.shell_safe(item.status.value),
        "FORMAT": formatters.shell_safe(item.format.value),
        #
        # numerical
        #
        "NEXT_EPISODE": formatters.shell_safe(
            f"Episode {item.next_airing.episode} on {formatters.format_date(item.next_airing.airing_at)}"
            if item.next_airing
            else "N/A"
        ),
        "EPISODES": formatters.shell_safe(str(item.episodes)),
        "SCORE": formatters.shell_safe(
            formatters.format_score_stars_full(item.average_score)
        ),
        "FAVOURITES": formatters.shell_safe(
            formatters.format_number_with_commas(item.favourites)
        ),
        "POPULARITY": formatters.shell_safe(
            formatters.format_number_with_commas(item.popularity)
        ),
        #
        # list
        #
        "GENRES": formatters.shell_safe(
            formatters.format_list_with_commas([v.value for v in item.genres])
        ),
        "TAGS": formatters.shell_safe(
            formatters.format_list_with_commas([t.name.value for t in item.tags])
        ),
        "STUDIOS": formatters.shell_safe(
            formatters.format_list_with_commas([t.name for t in item.studios if t.name])
        ),
        "SYNONYMNS": formatters.shell_safe(
            formatters.format_list_with_commas(item.synonymns)
        ),
        #
        # user
        #
        "USER_STATUS": formatters.shell_safe(
            item.user_status.status.value
            if item.user_status and item.user_status.status
            else "NOT_ON_LIST"
        ),
        "USER_PROGRESS": formatters.shell_safe(
            f"Episode {item.user_status.progress}" if item.user_status else "0"
        ),
        #
        # dates
        #
        "START_DATE": formatters.shell_safe(formatters.format_date(item.start_date)),
        "END_DATE": formatters.shell_safe(formatters.format_date(item.end_date)),
        #
        # big guy
        #
        "SYNOPSIS": formatters.shell_safe(description),
        #
        # Color codes
        #
        "C_TITLE": ansi.get_true_fg(HEADER_COLOR, bold=True),
        "C_KEY": ansi.get_true_fg(HEADER_COLOR, bold=True),
        "C_VALUE": ansi.get_true_fg(HEADER_COLOR, bold=True),
        "C_RULE": ansi.get_true_fg(SEPARATOR_COLOR, bold=True),
        "RESET": ansi.RESET,
    }

    for key, value in replacements.items():
        template = template.replace(f"{{{key}}}", value)

    return template


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
                # TODO: Come up with a better caching pattern for now just let it be remade
                if not (INFO_CACHE_DIR / hash_id).exists() or True:
                    info_text = _populate_info_template(item, config)
                    executor.submit(_save_info_text, info_text, hash_id)


def get_anime_preview(
    items: List[MediaItem], titles: List[str], config: AppConfig
) -> str:
    """
    Starts a background task to cache preview data and returns the fzf preview command
    by formatting a shell script template.
    """
    # Ensure cache directories exist on startup
    IMAGES_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    INFO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

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
    final_script = (
        template.replace("{preview_mode}", config.general.preview)
        .replace("{image_cache_path}", str(IMAGES_CACHE_DIR))
        .replace("{info_cache_path}", str(INFO_CACHE_DIR))
        .replace("{path_sep}", path_sep)
        .replace("{image_renderer}", config.general.image_renderer)
        .replace("{PREFIX}", "")
    )
    # )

    # Return the command for fzf to execute. `sh -c` is used to run the script string.
    # The -- "{}" ensures that the selected item is passed as the first argument ($1)
    # to the script, even if it contains spaces or special characters.
    os.environ["SHELL"] = "bash"
    return final_script


# --- Episode Preview Functionality ---


def _populate_episode_info_template(episode_data: dict, config: AppConfig) -> str:
    """
    Takes the episode_info.sh template and injects episode-specific formatted data.
    """
    template = EPISODE_INFO_SCRIPT_TEMPLATE_PATH.read_text(encoding="utf-8")

    HEADER_COLOR = config.fzf.preview_header_color.split(",")
    SEPARATOR_COLOR = config.fzf.preview_separator_color.split(",")

    # Escape all variables before injecting them into the script
    replacements = {
        "TITLE": formatters.shell_safe(episode_data.get("title", "Episode")),
        "SCORE": formatters.shell_safe("N/A"),  # Episodes don't have scores
        "STATUS": formatters.shell_safe(episode_data.get("status", "Available")),
        "FAVOURITES": formatters.shell_safe("N/A"),  # Episodes don't have favorites
        "GENRES": formatters.shell_safe(
            episode_data.get("duration", "Unknown duration")
        ),
        "SYNOPSIS": formatters.shell_safe(
            episode_data.get("description", "No episode description available.")
        ),
        # Color codes
        "C_TITLE": ansi.get_true_fg(HEADER_COLOR, bold=True),
        "C_KEY": ansi.get_true_fg(HEADER_COLOR, bold=True),
        "C_VALUE": ansi.get_true_fg(HEADER_COLOR, bold=True),
        "C_RULE": ansi.get_true_fg(SEPARATOR_COLOR, bold=True),
        "RESET": ansi.RESET,
    }

    for key, value in replacements.items():
        template = template.replace(f"{{{key}}}", value)

    return template


def _episode_cache_worker(episodes: List[str], anime: MediaItem, config: AppConfig):
    """Background task that fetches and saves episode preview data."""
    streaming_episodes = {ep.title: ep for ep in anime.streaming_episodes}

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        for episode_str in episodes:
            hash_id = _get_cache_hash(f"{anime.title.english}_Episode_{episode_str}")

            # Find matching streaming episode
            episode_data = None
            for title, ep in streaming_episodes.items():
                if f"Episode {episode_str} -" in title or title.endswith(
                    f" {episode_str}"
                ):
                    episode_data = {
                        "title": title,
                        "thumbnail": ep.thumbnail,
                        "description": f"Episode {episode_str} of {anime.title.english or anime.title.romaji}",
                        "duration": f"{anime.duration} min"
                        if anime.duration
                        else "Unknown duration",
                        "status": "Available",
                    }
                    break

            # Fallback if no streaming episode found
            if not episode_data:
                episode_data = {
                    "title": f"Episode {episode_str}",
                    "thumbnail": None,
                    "description": f"Episode {episode_str} of {anime.title.english or anime.title.romaji}",
                    "duration": f"{anime.duration} min"
                    if anime.duration
                    else "Unknown duration",
                    "status": "Available",
                }

            # Download thumbnail if available
            if episode_data["thumbnail"]:
                executor.submit(
                    _save_image_from_url, episode_data["thumbnail"], hash_id
                )

            # Generate and save episode info
            episode_info = _populate_episode_info_template(episode_data, config)
            executor.submit(_save_info_text, episode_info, hash_id)


def get_episode_preview(
    episodes: List[str], anime: MediaItem, config: AppConfig
) -> str:
    """
    Starts a background task to cache episode preview data and returns the fzf preview command.

    Args:
        episodes: List of episode numbers as strings
        anime: MediaItem containing the anime data with streaming episodes
        config: Application configuration

    Returns:
        FZF preview command string
    """
    # TODO: finish implementation of episode preview
    # Ensure cache directories exist
    IMAGES_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    INFO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Start background caching for episodes
    Thread(
        target=_episode_cache_worker, args=(episodes, anime, config), daemon=True
    ).start()

    # Read the shell script template
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
    final_script = (
        template.replace("{preview_mode}", config.general.preview)
        .replace("{image_cache_path}", str(IMAGES_CACHE_DIR))
        .replace("{info_cache_path}", str(INFO_CACHE_DIR))
        .replace("{path_sep}", path_sep)
        .replace("{image_renderer}", config.general.image_renderer)
        .replace("{PREFIX}", f"{anime.title.english}_Episode_")
    )

    os.environ["SHELL"] = "bash"
    return final_script
