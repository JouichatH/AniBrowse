import concurrent.futures
import logging
import os
from hashlib import sha256
from pathlib import Path
from threading import Thread
from typing import List

import httpx

from ...core.config import AppConfig
from ...core.constants import APP_CACHE_DIR, PLATFORM, SCRIPTS_DIR
from ...core.utils.file import AtomicWriter
from ...libs.api.types import MediaItem
from . import ansi, formatters

logger = logging.getLogger(__name__)

os.environ["SHELL"] = "bash"

PREVIEWS_CACHE_DIR = APP_CACHE_DIR / "previews"
IMAGES_CACHE_DIR = PREVIEWS_CACHE_DIR / "images"
INFO_CACHE_DIR = PREVIEWS_CACHE_DIR / "info"

FZF_SCRIPTS_DIR = SCRIPTS_DIR / "fzf"
TEMPLATE_PREVIEW_SCRIPT = Path(str(FZF_SCRIPTS_DIR / "preview.template.sh")).read_text(
    encoding="utf-8"
)
TEMPLATE_INFO_SCRIPT = Path(str(FZF_SCRIPTS_DIR / "info.template.sh")).read_text(
    encoding="utf-8"
)
TEMPLATE_EPISODE_INFO_SCRIPT = Path(
    str(FZF_SCRIPTS_DIR / "episode-info.template.sh")
).read_text(encoding="utf-8")


def get_anime_preview(
    items: List[MediaItem], titles: List[str], config: AppConfig
) -> str:
    # Ensure cache directories exist on startup
    IMAGES_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    INFO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    HEADER_COLOR = config.fzf.preview_header_color.split(",")
    SEPARATOR_COLOR = config.fzf.preview_separator_color.split(",")

    preview_script = TEMPLATE_PREVIEW_SCRIPT

    # Start the non-blocking background Caching
    Thread(target=_cache_worker, args=(items, titles, config), daemon=True).start()

    # Prepare values to inject into the template
    path_sep = "\\" if PLATFORM == "win32" else "/"

    # Format the template with the dynamic values
    replacements = {
        "PREVIEW_MODE": config.general.preview,
        "IMAGE_CACHE_PATH": str(IMAGES_CACHE_DIR),
        "INFO_CACHE_PATH": str(INFO_CACHE_DIR),
        "PATH_SEP": path_sep,
        "IMAGE_RENDERER": config.general.image_renderer,
        # Color codes
        "C_TITLE": ansi.get_true_fg(HEADER_COLOR, bold=True),
        "C_KEY": ansi.get_true_fg(HEADER_COLOR, bold=True),
        "C_VALUE": ansi.get_true_fg(HEADER_COLOR, bold=True),
        "C_RULE": ansi.get_true_fg(SEPARATOR_COLOR, bold=True),
        "RESET": ansi.RESET,
        "PREFIX": "",
    }

    for key, value in replacements.items():
        preview_script = preview_script.replace(f"{{{key}}}", value)

    return preview_script


def _cache_worker(media_items: List[MediaItem], titles: List[str], config: AppConfig):
    """The background task that fetches and saves all necessary preview data."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for media_item, title_str in zip(media_items, titles):
            hash_id = _get_cache_hash(title_str)
            if config.general.preview in ("full", "image") and media_item.cover_image:
                if not (IMAGES_CACHE_DIR / f"{hash_id}.png").exists():
                    executor.submit(
                        _save_image_from_url, media_item.cover_image.large, hash_id
                    )
            if config.general.preview in ("full", "text"):
                # TODO: Come up with a better caching pattern for now just let it be remade
                if not (INFO_CACHE_DIR / hash_id).exists() or True:
                    info_text = _populate_info_template(media_item, config)
                    executor.submit(_save_info_text, info_text, hash_id)


def _populate_info_template(media_item: MediaItem, config: AppConfig) -> str:
    """
    Takes the info.sh template and injects formatted, shell-safe data.
    """
    info_script = TEMPLATE_INFO_SCRIPT
    description = formatters.clean_html(
        media_item.description or "No description available."
    )

    # Escape all variables before injecting them into the script
    replacements = {
        "TITLE": formatters.shell_safe(
            media_item.title.english or media_item.title.romaji
        ),
        "STATUS": formatters.shell_safe(media_item.status.value),
        "FORMAT": formatters.shell_safe(media_item.format.value),
        "NEXT_EPISODE": formatters.shell_safe(
            f"Episode {media_item.next_airing.episode} on {formatters.format_date(media_item.next_airing.airing_at, '%A, %d %B %Y at %X)')}"
            if media_item.next_airing
            else "N/A"
        ),
        "EPISODES": formatters.shell_safe(str(media_item.episodes)),
        "DURATION": formatters.shell_safe(
            formatters.format_media_duration(media_item.duration)
        ),
        "SCORE": formatters.shell_safe(
            formatters.format_score_stars_full(media_item.average_score)
        ),
        "FAVOURITES": formatters.shell_safe(
            formatters.format_number_with_commas(media_item.favourites)
        ),
        "POPULARITY": formatters.shell_safe(
            formatters.format_number_with_commas(media_item.popularity)
        ),
        "GENRES": formatters.shell_safe(
            formatters.format_list_with_commas([v.value for v in media_item.genres])
        ),
        "TAGS": formatters.shell_safe(
            formatters.format_list_with_commas([t.name.value for t in media_item.tags])
        ),
        "STUDIOS": formatters.shell_safe(
            formatters.format_list_with_commas(
                [t.name for t in media_item.studios if t.name]
            )
        ),
        "SYNONYMNS": formatters.shell_safe(
            formatters.format_list_with_commas(media_item.synonymns)
        ),
        "USER_STATUS": formatters.shell_safe(
            media_item.user_status.status.value
            if media_item.user_status and media_item.user_status.status
            else "NOT_ON_LIST"
        ),
        "USER_PROGRESS": formatters.shell_safe(
            f"Episode {media_item.user_status.progress}"
            if media_item.user_status
            else "0"
        ),
        "START_DATE": formatters.shell_safe(
            formatters.format_date(media_item.start_date)
        ),
        "END_DATE": formatters.shell_safe(formatters.format_date(media_item.end_date)),
        "SYNOPSIS": formatters.shell_safe(description),
    }

    for key, value in replacements.items():
        info_script = info_script.replace(f"{{{key}}}", value)

    return info_script


def get_episode_preview(
    episodes: List[str], media_item: MediaItem, config: AppConfig
) -> str:
    IMAGES_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    INFO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    HEADER_COLOR = config.fzf.preview_header_color.split(",")
    SEPARATOR_COLOR = config.fzf.preview_separator_color.split(",")

    preview_script = TEMPLATE_PREVIEW_SCRIPT
    # Start background caching for episodes
    Thread(
        target=_episode_cache_worker, args=(episodes, media_item, config), daemon=True
    ).start()

    # Prepare values to inject into the template
    path_sep = "\\" if PLATFORM == "win32" else "/"

    # Format the template with the dynamic values
    replacements = {
        "PREVIEW_MODE": config.general.preview,
        "IMAGE_CACHE_PATH": str(IMAGES_CACHE_DIR),
        "INFO_CACHE_PATH": str(INFO_CACHE_DIR),
        "PATH_SEP": path_sep,
        "IMAGE_RENDERER": config.general.image_renderer,
        # Color codes
        "C_TITLE": ansi.get_true_fg(HEADER_COLOR, bold=True),
        "C_KEY": ansi.get_true_fg(HEADER_COLOR, bold=True),
        "C_VALUE": ansi.get_true_fg(HEADER_COLOR, bold=True),
        "C_RULE": ansi.get_true_fg(SEPARATOR_COLOR, bold=True),
        "RESET": ansi.RESET,
        "PREFIX": f"{media_item.title.english}_Episode_",
    }

    for key, value in replacements.items():
        preview_script = preview_script.replace(f"{{{key}}}", value)

    return preview_script


def _episode_cache_worker(
    episodes: List[str], media_item: MediaItem, config: AppConfig
):
    """Background task that fetches and saves episode preview data."""
    streaming_episodes = {ep.title: ep for ep in media_item.streaming_episodes}

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        for episode_str in episodes:
            hash_id = _get_cache_hash(
                f"{media_item.title.english}_Episode_{episode_str}"
            )

            # Find matching streaming episode
            title = None
            thumbnail = None
            for title, ep in streaming_episodes.items():
                if f"Episode {episode_str} -" in title or title.endswith(
                    f" {episode_str}"
                ):
                    title = title
                    thumbnail = ep.thumbnail
                    break

            # Fallback if no streaming episode found
            if not title:
                title = f"Episode {episode_str}"

            # Download thumbnail if available
            if thumbnail:
                executor.submit(_save_image_from_url, thumbnail, hash_id)

            # Generate and save episode info
            episode_info = _populate_episode_info_template(config, title, media_item)
            executor.submit(_save_info_text, episode_info, hash_id)


def _populate_episode_info_template(
    config: AppConfig, title: str, media_item: MediaItem
) -> str:
    """
    Takes the episode_info.sh template and injects episode-specific formatted data.
    """
    episode_info_script = TEMPLATE_EPISODE_INFO_SCRIPT

    replacements = {
        "TITLE": formatters.shell_safe(title),
        "NEXT_EPISODE": formatters.shell_safe(
            f"Episode {media_item.next_airing.episode} on {formatters.format_date(media_item.next_airing.airing_at, '%A, %d %B %Y at %X)')}"
            if media_item.next_airing
            else "N/A"
        ),
        "DURATION": formatters.format_media_duration(media_item.duration),
        "STATUS": formatters.shell_safe(media_item.status.value),
        "EPISODES": formatters.shell_safe(str(media_item.episodes)),
        "USER_STATUS": formatters.shell_safe(
            media_item.user_status.status.value
            if media_item.user_status and media_item.user_status.status
            else "NOT_ON_LIST"
        ),
        "USER_PROGRESS": formatters.shell_safe(
            f"Episode {media_item.user_status.progress}"
            if media_item.user_status
            else "0"
        ),
        "START_DATE": formatters.shell_safe(
            formatters.format_date(media_item.start_date)
        ),
        "END_DATE": formatters.shell_safe(formatters.format_date(media_item.end_date)),
    }

    for key, value in replacements.items():
        episode_info_script = episode_info_script.replace(f"{{{key}}}", value)

    return episode_info_script


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
