"""
Core download manager for tracking and managing anime downloads.

This module provides the central DownloadManager class that handles all download
tracking operations, integrates with the existing downloader infrastructure,
and manages the storage of download records.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from ....core.config.model import DownloadsConfig
from ....core.constants import APP_CACHE_DIR, APP_DATA_DIR
from ....core.downloader import create_downloader
from ....libs.api.types import MediaItem
from .models import (
    DownloadIndex,
    DownloadQueue,
    DownloadQueueItem,
    EpisodeDownload,
    MediaDownloadRecord,
    MediaIndexEntry,
)

logger = logging.getLogger(__name__)


class DownloadService:
    """
    Core download manager using Pydantic models and integrating with existing infrastructure.

    Manages download tracking, queue operations, and storage with atomic operations
    and thread safety. Integrates with the existing downloader infrastructure.
    """

    def __init__(self, config: DownloadsConfig):
        self.config = config
        self.downloads_dir = config.downloads_dir

        # Storage directories
        self.tracking_dir = APP_DATA_DIR / "downloads"
        self.cache_dir = APP_CACHE_DIR / "downloads"
        self.media_dir = self.tracking_dir / "media"

        # File paths
        self.index_file = self.tracking_dir / "index.json"
        self.queue_file = self.tracking_dir / "queue.json"

        # Thread safety
        self._lock = threading.RLock()
        self._loaded_records: Dict[int, MediaDownloadRecord] = {}
        self._index: Optional[DownloadIndex] = None
        self._queue: Optional[DownloadQueue] = None

        # Initialize storage and downloader
        self._initialize_storage()

        # Use existing downloader infrastructure
        try:
            self.downloader = create_downloader(config)
        except Exception as e:
            logger.warning(f"Failed to initialize downloader: {e}")
            self.downloader = None

    def _initialize_storage(self) -> None:
        """Initialize storage directories and files."""
        try:
            # Create directories
            self.tracking_dir.mkdir(parents=True, exist_ok=True)
            self.media_dir.mkdir(parents=True, exist_ok=True)
            self.cache_dir.mkdir(parents=True, exist_ok=True)

            # Create subdirectories for cache
            (self.cache_dir / "thumbnails").mkdir(exist_ok=True)
            (self.cache_dir / "metadata").mkdir(exist_ok=True)
            (self.cache_dir / "temp").mkdir(exist_ok=True)

            # Initialize index if it doesn't exist
            if not self.index_file.exists():
                self._create_empty_index()

            # Initialize queue if it doesn't exist
            if not self.queue_file.exists():
                self._create_empty_queue()

        except Exception as e:
            logger.error(f"Failed to initialize download storage: {e}")
            raise

    def _create_empty_index(self) -> None:
        """Create an empty download index."""
        empty_index = DownloadIndex()
        self._save_index(empty_index)

    def _create_empty_queue(self) -> None:
        """Create an empty download queue."""
        empty_queue = DownloadQueue(max_size=self.config.queue_max_size)
        self._save_queue(empty_queue)

    def _load_index(self) -> DownloadIndex:
        """Load the download index with Pydantic validation."""
        if self._index is not None:
            return self._index

        try:
            if not self.index_file.exists():
                self._create_empty_index()

            with open(self.index_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._index = DownloadIndex.model_validate(data)
            return self._index

        except Exception as e:
            logger.error(f"Failed to load download index: {e}")
            # Create new empty index as fallback
            self._create_empty_index()
            return self._load_index()

    def _save_index(self, index: DownloadIndex) -> None:
        """Save index with atomic write operation."""
        temp_file = self.index_file.with_suffix(".tmp")

        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(
                    index.model_dump(), f, indent=2, ensure_ascii=False, default=str
                )

            # Atomic replace
            temp_file.replace(self.index_file)
            self._index = index

        except Exception as e:
            logger.error(f"Failed to save download index: {e}")
            if temp_file.exists():
                temp_file.unlink()
            raise

    def _load_queue(self) -> DownloadQueue:
        """Load the download queue with Pydantic validation."""
        if self._queue is not None:
            return self._queue

        try:
            if not self.queue_file.exists():
                self._create_empty_queue()

            with open(self.queue_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._queue = DownloadQueue.model_validate(data)
            return self._queue

        except Exception as e:
            logger.error(f"Failed to load download queue: {e}")
            # Create new empty queue as fallback
            self._create_empty_queue()
            return self._load_queue()

    def _save_queue(self, queue: DownloadQueue) -> None:
        """Save queue with atomic write operation."""
        temp_file = self.queue_file.with_suffix(".tmp")

        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(
                    queue.model_dump(), f, indent=2, ensure_ascii=False, default=str
                )

            # Atomic replace
            temp_file.replace(self.queue_file)
            self._queue = queue

        except Exception as e:
            logger.error(f"Failed to save download queue: {e}")
            if temp_file.exists():
                temp_file.unlink()
            raise

    def get_download_record(self, media_id: int) -> Optional[MediaDownloadRecord]:
        """Get download record for an anime with caching."""
        with self._lock:
            # Check cache first
            if media_id in self._loaded_records:
                return self._loaded_records[media_id]

            try:
                record_file = self.media_dir / f"{media_id}.json"

                if not record_file.exists():
                    return None

                with open(record_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                record = MediaDownloadRecord.model_validate(data)

                # Cache the record
                self._loaded_records[media_id] = record

                return record

            except Exception as e:
                logger.error(
                    f"Failed to load download record for media {media_id}: {e}"
                )
                return None

    def save_download_record(self, record: MediaDownloadRecord) -> bool:
        """Save a download record with atomic operation."""
        with self._lock:
            try:
                media_id = record.media_item.id
                record_file = self.media_dir / f"{media_id}.json"
                temp_file = record_file.with_suffix(".tmp")

                # Update last_modified timestamp
                record.update_last_modified()

                # Write to temp file first
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(
                        record.model_dump(),
                        f,
                        indent=2,
                        ensure_ascii=False,
                        default=str,
                    )

                # Atomic replace
                temp_file.replace(record_file)

                # Update cache
                self._loaded_records[media_id] = record

                # Update index
                index = self._load_index()
                index.add_media_entry(record)
                self._save_index(index)

                logger.debug(f"Saved download record for media {media_id}")
                return True

            except Exception as e:
                logger.error(f"Failed to save download record: {e}")
                if temp_file.exists():
                    temp_file.unlink()
                return False

    def add_to_queue(
        self,
        media_item: MediaItem,
        episodes: List[int],
        quality: Optional[str] = None,
        priority: int = 0,
    ) -> bool:
        """Add episodes to download queue."""
        with self._lock:
            try:
                queue = self._load_queue()
                quality = quality or self.config.preferred_quality

                success_count = 0
                for episode in episodes:
                    queue_item = DownloadQueueItem(
                        media_id=media_item.id,
                        episode_number=episode,
                        priority=priority,
                        quality_preference=quality,
                        max_retries=self.config.retry_attempts,
                    )

                    if queue.add_item(queue_item):
                        success_count += 1
                        logger.info(
                            f"Added episode {episode} of {media_item.title.english or media_item.title.romaji} to download queue"
                        )

                if success_count > 0:
                    self._save_queue(queue)

                    # Create download record if it doesn't exist
                    if not self.get_download_record(media_item.id):
                        download_path = self.downloads_dir / self._sanitize_filename(
                            media_item.title.english
                            or media_item.title.romaji
                            or f"Anime_{media_item.id}"
                        )

                        record = MediaDownloadRecord(
                            media_item=media_item,
                            download_path=download_path,
                            preferred_quality=quality,
                        )
                        self.save_download_record(record)

                return success_count > 0

            except Exception as e:
                logger.error(f"Failed to add episodes to queue: {e}")
                return False

    def get_next_download(self) -> Optional[DownloadQueueItem]:
        """Get the next item from the download queue."""
        with self._lock:
            try:
                queue = self._load_queue()
                return queue.get_next_item()

            except Exception as e:
                logger.error(f"Failed to get next download: {e}")
                return None

    def mark_download_started(self, media_id: int, episode: int) -> bool:
        """Mark an episode download as started."""
        with self._lock:
            try:
                record = self.get_download_record(media_id)
                if not record:
                    return False

                # Create episode download entry
                download_path = record.download_path / f"Episode_{episode:02d}.mkv"

                episode_download = EpisodeDownload(
                    episode_number=episode,
                    file_path=download_path,
                    file_size=0,
                    quality=record.preferred_quality,
                    source_provider="unknown",  # Will be updated by actual downloader
                    status="downloading",
                )

                # Update record
                new_episodes = record.episodes.copy()
                new_episodes[episode] = episode_download

                updated_record = record.model_copy(update={"episodes": new_episodes})
                self.save_download_record(updated_record)

                return True

            except Exception as e:
                logger.error(f"Failed to mark download started: {e}")
                return False

    def mark_download_completed(
        self,
        media_id: int,
        episode: int,
        file_path: Path,
        file_size: int,
        checksum: Optional[str] = None,
    ) -> bool:
        """Mark an episode download as completed."""
        with self._lock:
            try:
                record = self.get_download_record(media_id)
                if not record or episode not in record.episodes:
                    return False

                # Update episode download
                episode_download = record.episodes[episode]
                updated_episode = episode_download.model_copy(
                    update={
                        "file_path": file_path,
                        "file_size": file_size,
                        "status": "completed",
                        "download_progress": 1.0,
                        "checksum": checksum,
                    }
                )

                # Update record
                new_episodes = record.episodes.copy()
                new_episodes[episode] = updated_episode

                updated_record = record.model_copy(update={"episodes": new_episodes})
                self.save_download_record(updated_record)

                # Remove from queue
                queue = self._load_queue()
                queue.remove_item(media_id, episode)
                self._save_queue(queue)

                logger.info(
                    f"Marked episode {episode} of media {media_id} as completed"
                )
                return True

            except Exception as e:
                logger.error(f"Failed to mark download completed: {e}")
                return False

    def mark_download_failed(
        self, media_id: int, episode: int, error_message: str
    ) -> bool:
        """Mark an episode download as failed."""
        with self._lock:
            try:
                record = self.get_download_record(media_id)
                if not record or episode not in record.episodes:
                    return False

                # Update episode download
                episode_download = record.episodes[episode]
                updated_episode = episode_download.model_copy(
                    update={"status": "failed", "error_message": error_message}
                )

                # Update record
                new_episodes = record.episodes.copy()
                new_episodes[episode] = updated_episode

                updated_record = record.model_copy(update={"episodes": new_episodes})
                self.save_download_record(updated_record)

                logger.warning(
                    f"Marked episode {episode} of media {media_id} as failed: {error_message}"
                )
                return True

            except Exception as e:
                logger.error(f"Failed to mark download failed: {e}")
                return False

    def list_downloads(
        self, status_filter: Optional[str] = None, limit: Optional[int] = None
    ) -> List[MediaDownloadRecord]:
        """List download records with optional filtering."""
        try:
            index = self._load_index()
            records = []

            media_ids = list(index.media_index.keys())
            if limit:
                media_ids = media_ids[:limit]

            for media_id in media_ids:
                record = self.get_download_record(media_id)
                if record is None:
                    continue

                if status_filter and record.status != status_filter:
                    continue

                records.append(record)

            # Sort by last updated (most recent first)
            records.sort(key=lambda x: x.last_updated, reverse=True)

            return records

        except Exception as e:
            logger.error(f"Failed to list downloads: {e}")
            return []

    def cleanup_failed_downloads(self) -> int:
        """Clean up old failed downloads based on retention policy."""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)
            cleaned_count = 0

            for record in self.list_downloads():
                episodes_to_remove = []

                for episode_num, episode_download in record.episodes.items():
                    if (
                        episode_download.status == "failed"
                        and episode_download.download_date < cutoff_date
                    ):
                        episodes_to_remove.append(episode_num)

                if episodes_to_remove:
                    new_episodes = record.episodes.copy()
                    for episode_num in episodes_to_remove:
                        del new_episodes[episode_num]
                        cleaned_count += 1

                    updated_record = record.model_copy(
                        update={"episodes": new_episodes}
                    )
                    self.save_download_record(updated_record)

            logger.info(f"Cleaned up {cleaned_count} failed downloads")
            return cleaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup failed downloads: {e}")
            return 0

    def get_download_stats(self) -> Dict:
        """Get download statistics."""
        try:
            index = self._load_index()

            stats = {
                "total_anime": index.media_count,
                "total_episodes": index.total_episodes,
                "total_size_gb": round(index.total_size_gb, 2),
                "completion_stats": index.completion_stats,
                "queue_size": len(self._load_queue().items),
            }

            return stats

        except Exception as e:
            logger.error(f"Failed to get download stats: {e}")
            return {}

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility."""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, "_")

        # Limit length
        if len(filename) > 100:
            filename = filename[:100]

        return filename.strip()


# Global manager instance
_download_manager: Optional[DownloadManager] = None


def get_download_manager(config: DownloadsConfig) -> DownloadManager:
    """Get or create the global download manager instance."""
    global _download_manager

    if _download_manager is None:
        _download_manager = DownloadManager(config)

    return _download_manager
