"""
Preview-specific background workers for caching anime and episode data.

This module provides specialized workers for handling anime preview caching,
including image downloads and info text generation with proper lifecycle management.
"""

import logging
from typing import List, Optional

import httpx

from ...core.config import AppConfig
from ...core.constants import SCRIPTS_DIR
from ...core.utils import formatter
from ...core.utils.concurrency import (
    ManagedBackgroundWorker,
    WorkerTask,
    thread_manager,
)
from ...core.utils.file import AtomicWriter
from ...libs.media_api.types import MediaItem

logger = logging.getLogger(__name__)
FZF_SCRIPTS_DIR = SCRIPTS_DIR / "fzf"

TEMPLATE_INFO_SCRIPT = (FZF_SCRIPTS_DIR / "info.template.sh").read_text(
    encoding="utf-8"
)
TEMPLATE_EPISODE_INFO_SCRIPT = (FZF_SCRIPTS_DIR / "episode-info.template.sh").read_text(
    encoding="utf-8"
)


class PreviewCacheWorker(ManagedBackgroundWorker):
    """
    Specialized background worker for caching anime preview data.

    Handles downloading images and generating info text for anime previews
    with proper error handling and resource management.
    """

    def __init__(self, images_cache_dir, info_cache_dir, max_workers: int = 10):
        """
        Initialize the preview cache worker.

        Args:
            images_cache_dir: Directory to cache images
            info_cache_dir: Directory to cache info text
            max_workers: Maximum number of concurrent workers
        """
        super().__init__(max_workers=max_workers, name="PreviewCacheWorker")
        self.images_cache_dir = images_cache_dir
        self.info_cache_dir = info_cache_dir
        self._http_client: Optional[httpx.Client] = None

    def start(self) -> None:
        """Start the worker and initialize HTTP client."""
        super().start()
        self._http_client = httpx.Client(
            timeout=20.0,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=self.max_workers),
        )
        logger.debug("PreviewCacheWorker HTTP client initialized")

    def shutdown(self, wait: bool = True, timeout: Optional[float] = 30.0) -> None:
        """Shutdown the worker and cleanup HTTP client."""
        super().shutdown(wait=wait, timeout=timeout)
        if self._http_client:
            self._http_client.close()
            self._http_client = None
            logger.debug("PreviewCacheWorker HTTP client closed")

    def cache_anime_previews(
        self, media_items: List[MediaItem], titles: List[str], config: AppConfig
    ) -> None:
        """
        Cache preview data for multiple anime items.

        Args:
            media_items: List of media items to cache
            titles: Corresponding titles for each media item
            config: Application configuration
        """
        if not self.is_running():
            raise RuntimeError("PreviewCacheWorker is not running")

        for media_item, title_str in zip(media_items, titles):
            hash_id = self._get_cache_hash(title_str)

            # Submit image download task if needed
            if config.general.preview in ("full", "image") and media_item.cover_image:
                image_path = self.images_cache_dir / f"{hash_id}.png"
                if not image_path.exists():
                    self.submit_function(
                        self._download_and_save_image,
                        media_item.cover_image.large,
                        hash_id,
                    )

            # Submit info generation task if needed
            if config.general.preview in ("full", "text"):
                info_path = self.info_cache_dir / hash_id
                info_text = self._generate_info_text(media_item, config)
                self.submit_function(self._save_info_text, info_text, hash_id)

    def _download_and_save_image(self, url: str, hash_id: str) -> None:
        """Download an image and save it to cache."""
        if not self._http_client:
            raise RuntimeError("HTTP client not initialized")

        image_path = self.images_cache_dir / f"{hash_id}.png"

        try:
            with self._http_client.stream("GET", url) as response:
                response.raise_for_status()

                with AtomicWriter(image_path, "wb", encoding=None) as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)

                logger.debug(f"Successfully cached image: {hash_id}")

        except Exception as e:
            logger.error(f"Failed to download image {url}: {e}")
            raise

    def _generate_info_text(self, media_item: MediaItem, config: AppConfig) -> str:
        """Generate formatted info text for a media item."""
        # Import here to avoid circular imports
        info_script = TEMPLATE_INFO_SCRIPT
        description = formatter.clean_html(
            media_item.description or "No description available."
        )

        # Escape all variables before injecting them into the script
        replacements = {
            "TITLE": formatter.shell_safe(
                media_item.title.english or media_item.title.romaji
            ),
            "STATUS": formatter.shell_safe(media_item.status.value),
            "FORMAT": formatter.shell_safe(
                media_item.format.value if media_item.format else "UNKNOWN"
            ),
            "NEXT_EPISODE": formatter.shell_safe(
                f"Episode {media_item.next_airing.episode} on {formatter.format_date(media_item.next_airing.airing_at, '%A, %d %B %Y at %X)')}"
                if media_item.next_airing
                else "N/A"
            ),
            "EPISODES": formatter.shell_safe(str(media_item.episodes)),
            "DURATION": formatter.shell_safe(
                formatter.format_media_duration(media_item.duration)
            ),
            "SCORE": formatter.shell_safe(
                formatter.format_score_stars_full(media_item.average_score)
            ),
            "FAVOURITES": formatter.shell_safe(
                formatter.format_number_with_commas(media_item.favourites)
            ),
            "POPULARITY": formatter.shell_safe(
                formatter.format_number_with_commas(media_item.popularity)
            ),
            "GENRES": formatter.shell_safe(
                formatter.format_list_with_commas([v.value for v in media_item.genres])
            ),
            "TAGS": formatter.shell_safe(
                formatter.format_list_with_commas(
                    [t.name.value for t in media_item.tags]
                )
            ),
            "STUDIOS": formatter.shell_safe(
                formatter.format_list_with_commas(
                    [t.name for t in media_item.studios if t.name]
                )
            ),
            "SYNONYMNS": formatter.shell_safe(
                formatter.format_list_with_commas(media_item.synonymns)
            ),
            "USER_STATUS": formatter.shell_safe(
                media_item.user_status.status.value
                if media_item.user_status and media_item.user_status.status
                else "NOT_ON_LIST"
            ),
            "USER_PROGRESS": formatter.shell_safe(
                f"Episode {media_item.user_status.progress}"
                if media_item.user_status
                else "0"
            ),
            "START_DATE": formatter.shell_safe(
                formatter.format_date(media_item.start_date)
            ),
            "END_DATE": formatter.shell_safe(
                formatter.format_date(media_item.end_date)
            ),
            "SYNOPSIS": formatter.shell_safe(description),
        }

        for key, value in replacements.items():
            info_script = info_script.replace(f"{{{key}}}", value)

        return info_script

    def _save_info_text(self, info_text: str, hash_id: str) -> None:
        """Save info text to cache."""
        try:
            info_path = self.info_cache_dir / hash_id
            with AtomicWriter(info_path) as f:
                f.write(info_text)
            logger.debug(f"Successfully cached info: {hash_id}")
        except IOError as e:
            logger.error(f"Failed to write info cache for {hash_id}: {e}")
            raise

    def _get_cache_hash(self, text: str) -> str:
        """Generate a cache hash for the given text."""
        from hashlib import sha256

        return sha256(text.encode("utf-8")).hexdigest()

    def _on_task_completed(self, task: WorkerTask, future) -> None:
        """Handle task completion with enhanced logging."""
        super()._on_task_completed(task, future)

        if future.exception():
            logger.warning(f"Preview cache task failed: {future.exception()}")
        else:
            logger.debug("Preview cache task completed successfully")


class EpisodeCacheWorker(ManagedBackgroundWorker):
    """
    Specialized background worker for caching episode preview data.

    Handles episode-specific caching including thumbnails and episode info
    with proper error handling and resource management.
    """

    def __init__(self, images_cache_dir, info_cache_dir, max_workers: int = 5):
        """
        Initialize the episode cache worker.

        Args:
            images_cache_dir: Directory to cache images
            info_cache_dir: Directory to cache info text
            max_workers: Maximum number of concurrent workers
        """
        super().__init__(max_workers=max_workers, name="EpisodeCacheWorker")
        self.images_cache_dir = images_cache_dir
        self.info_cache_dir = info_cache_dir
        self._http_client: Optional[httpx.Client] = None

    def start(self) -> None:
        """Start the worker and initialize HTTP client."""
        super().start()
        self._http_client = httpx.Client(
            timeout=20.0,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=self.max_workers),
        )
        logger.debug("EpisodeCacheWorker HTTP client initialized")

    def shutdown(self, wait: bool = True, timeout: Optional[float] = 30.0) -> None:
        """Shutdown the worker and cleanup HTTP client."""
        super().shutdown(wait=wait, timeout=timeout)
        if self._http_client:
            self._http_client.close()
            self._http_client = None
            logger.debug("EpisodeCacheWorker HTTP client closed")

    def cache_episode_previews(
        self, episodes: List[str], media_item: MediaItem, config: AppConfig
    ) -> None:
        """
        Cache preview data for multiple episodes.

        Args:
            episodes: List of episode identifiers
            media_item: Media item containing episode data
            config: Application configuration
        """
        if not self.is_running():
            raise RuntimeError("EpisodeCacheWorker is not running")

        streaming_episodes = media_item.streaming_episodes

        for episode_str in episodes:
            hash_id = self._get_cache_hash(
                f"{media_item.title.english}_Episode_{episode_str}"
            )

            # Find episode data
            episode_data = streaming_episodes.get(episode_str)
            title = episode_data.title if episode_data else f"Episode {episode_str}"
            thumbnail = None

            if episode_data and episode_data.thumbnail:
                thumbnail = episode_data.thumbnail
            elif media_item.cover_image:
                thumbnail = media_item.cover_image.large

            # Submit thumbnail download task
            if thumbnail:
                self.submit_function(self._download_and_save_image, thumbnail, hash_id)

            # Submit episode info generation task
            episode_info = self._generate_episode_info(config, title, media_item)
            self.submit_function(self._save_info_text, episode_info, hash_id)

    def _download_and_save_image(self, url: str, hash_id: str) -> None:
        """Download an image and save it to cache."""
        if not self._http_client:
            raise RuntimeError("HTTP client not initialized")

        image_path = self.images_cache_dir / f"{hash_id}.png"

        try:
            with self._http_client.stream("GET", url) as response:
                response.raise_for_status()

                with AtomicWriter(image_path, "wb", encoding=None) as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)

                logger.debug(f"Successfully cached episode image: {hash_id}")

        except Exception as e:
            logger.error(f"Failed to download episode image {url}: {e}")
            raise

    def _generate_episode_info(
        self, config: AppConfig, title: str, media_item: MediaItem
    ) -> str:
        """Generate formatted episode info text."""
        episode_info_script = TEMPLATE_EPISODE_INFO_SCRIPT

        replacements = {
            "TITLE": formatter.shell_safe(title),
            "NEXT_EPISODE": formatter.shell_safe(
                f"Episode {media_item.next_airing.episode} on {formatter.format_date(media_item.next_airing.airing_at, '%A, %d %B %Y at %X)')}"
                if media_item.next_airing
                else "N/A"
            ),
            "DURATION": formatter.format_media_duration(media_item.duration),
            "STATUS": formatter.shell_safe(media_item.status.value),
            "EPISODES": formatter.shell_safe(str(media_item.episodes)),
            "USER_STATUS": formatter.shell_safe(
                media_item.user_status.status.value
                if media_item.user_status and media_item.user_status.status
                else "NOT_ON_LIST"
            ),
            "USER_PROGRESS": formatter.shell_safe(
                f"Episode {media_item.user_status.progress}"
                if media_item.user_status
                else "0"
            ),
            "START_DATE": formatter.shell_safe(
                formatter.format_date(media_item.start_date)
            ),
            "END_DATE": formatter.shell_safe(
                formatter.format_date(media_item.end_date)
            ),
        }

        for key, value in replacements.items():
            episode_info_script = episode_info_script.replace(f"{{{key}}}", value)

        return episode_info_script

    def _save_info_text(self, info_text: str, hash_id: str) -> None:
        """Save episode info text to cache."""
        try:
            info_path = self.info_cache_dir / hash_id
            with AtomicWriter(info_path) as f:
                f.write(info_text)
            logger.debug(f"Successfully cached episode info: {hash_id}")
        except IOError as e:
            logger.error(f"Failed to write episode info cache for {hash_id}: {e}")
            raise

    def _get_cache_hash(self, text: str) -> str:
        """Generate a cache hash for the given text."""
        from hashlib import sha256

        return sha256(text.encode("utf-8")).hexdigest()

    def _on_task_completed(self, task: WorkerTask, future) -> None:
        """Handle task completion with enhanced logging."""
        super()._on_task_completed(task, future)

        if future.exception():
            logger.warning(f"Episode cache task failed: {future.exception()}")
        else:
            logger.debug("Episode cache task completed successfully")


class PreviewWorkerManager:
    """
    High-level manager for preview caching workers.

    Provides a simple interface for managing both anime and episode preview
    caching workers with automatic lifecycle management.
    """

    def __init__(self, images_cache_dir, info_cache_dir):
        """
        Initialize the preview worker manager.

        Args:
            images_cache_dir: Directory to cache images
            info_cache_dir: Directory to cache info text
        """
        self.images_cache_dir = images_cache_dir
        self.info_cache_dir = info_cache_dir
        self._preview_worker: Optional[PreviewCacheWorker] = None
        self._episode_worker: Optional[EpisodeCacheWorker] = None

    def get_preview_worker(self) -> PreviewCacheWorker:
        """Get or create the preview cache worker."""
        if self._preview_worker is None or not self._preview_worker.is_running():
            if self._preview_worker:
                # Clean up old worker
                thread_manager.shutdown_worker("preview_cache_worker")

            self._preview_worker = PreviewCacheWorker(
                self.images_cache_dir, self.info_cache_dir
            )
            self._preview_worker.start()
            thread_manager.register_worker("preview_cache_worker", self._preview_worker)

        return self._preview_worker

    def get_episode_worker(self) -> EpisodeCacheWorker:
        """Get or create the episode cache worker."""
        if self._episode_worker is None or not self._episode_worker.is_running():
            if self._episode_worker:
                # Clean up old worker
                thread_manager.shutdown_worker("episode_cache_worker")

            self._episode_worker = EpisodeCacheWorker(
                self.images_cache_dir, self.info_cache_dir
            )
            self._episode_worker.start()
            thread_manager.register_worker("episode_cache_worker", self._episode_worker)

        return self._episode_worker

    def shutdown_all(self, wait: bool = True, timeout: Optional[float] = 30.0) -> None:
        """Shutdown all managed workers."""
        thread_manager.shutdown_worker(
            "preview_cache_worker", wait=wait, timeout=timeout
        )
        thread_manager.shutdown_worker(
            "episode_cache_worker", wait=wait, timeout=timeout
        )
        self._preview_worker = None
        self._episode_worker = None

    def get_status(self) -> dict:
        """Get status of all managed workers."""
        return {
            "preview_worker": self._preview_worker.get_completion_stats()
            if self._preview_worker
            else None,
            "episode_worker": self._episode_worker.get_completion_stats()
            if self._episode_worker
            else None,
        }

    def __enter__(self):
        """Context manager entry - workers are created on demand."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic cleanup."""
        self.shutdown_all(wait=False, timeout=5.0)
