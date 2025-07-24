import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List, Optional

from ....core.config.model import MediaRegistryConfig
from ....core.exceptions import FastAnimeError
from ....core.utils.file import AtomicWriter, FileLock, check_file_modified
from ....libs.media_api.params import MediaSearchParams
from ....libs.media_api.types import (
    MediaItem,
    MediaSearchResult,
    PageInfo,
    UserMediaListStatus,
)
from .filters import MediaFilter
from .models import (
    REGISTRY_VERSION,
    MediaRecord,
    MediaRegistryIndex,
    MediaRegistryIndexEntry,
)

logger = logging.getLogger(__name__)


class MediaRegistryService:
    def __init__(self, media_api: str, config: MediaRegistryConfig):
        self.config = config
        self.media_registry_dir = self.config.media_dir / media_api
        self._media_api = media_api
        self._ensure_directories()
        self._index = None
        self._index_file = self.config.index_dir / "registry.json"
        self._index_file_modified_time = 0
        _lock_file = self.config.media_dir / "registry.lock"
        self._lock = FileLock(_lock_file)

    def _ensure_directories(self) -> None:
        """Ensure registry directories exist."""
        try:
            self.media_registry_dir.mkdir(parents=True, exist_ok=True)
            self.config.index_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create registry directories: {e}")

    def _load_index(self) -> MediaRegistryIndex:
        """Load or create the registry index."""
        self._index_file_modified_time, is_modified = check_file_modified(
            self._index_file, self._index_file_modified_time
        )
        if not is_modified and self._index is not None:
            return self._index
        if self._index_file.exists():
            with self._index_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self._index = MediaRegistryIndex.model_validate(data)
        else:
            self._index = MediaRegistryIndex()
            self._save_index(self._index)

        # check if there was a major change in the registry
        if self._index.version[0] != REGISTRY_VERSION[0]:
            raise FastAnimeError(
                f"Incompatible registry version of {self._index.version}. Current registry supports version {REGISTRY_VERSION}. Please migrate your registry using the migrator"
            )

        logger.debug(f"Loaded registry index with {self._index.media_count} entries")
        return self._index

    def _save_index(self, index: MediaRegistryIndex):
        """Save the registry index."""
        with self._lock:
            index.last_updated = datetime.now()
            with AtomicWriter(self._index_file) as f:
                json.dump(index.model_dump(mode="json"), f, indent=2)

            logger.debug("saved registry index")

    def get_media_index_entry(self, media_id: int) -> Optional[MediaRegistryIndexEntry]:
        index = self._load_index()
        return index.media_index.get(f"{self._media_api}_{media_id}")

    def _get_media_file_path(self, media_id: int) -> Path:
        """Get file path for media record."""
        return self.media_registry_dir / f"{media_id}.json"

    def get_media_record(self, media_id: int) -> Optional[MediaRecord]:
        record_file = self._get_media_file_path(media_id)
        if not record_file.exists():
            return None

        data = json.load(record_file.open(mode="r", encoding="utf-8"))

        record = MediaRecord.model_validate(data)

        logger.debug(f"Loaded media record for {media_id}")
        return record

    def get_or_create_index_entry(self, media_id: int) -> MediaRegistryIndexEntry:
        index_entry = self.get_media_index_entry(media_id)
        if not index_entry:
            index = self._load_index()
            index_entry = MediaRegistryIndexEntry(
                media_id=media_id,
                media_api=self._media_api,  # pyright:ignore
            )
            index.media_index[f"{self._media_api}_{media_id}"] = index_entry
            self._save_index(index)
            return index_entry
        return index_entry

    def save_media_index_entry(self, index_entry: MediaRegistryIndexEntry) -> bool:
        index = self._load_index()
        index.media_index[f"{self._media_api}_{index_entry.media_id}"] = index_entry
        self._save_index(index)

        logger.debug(f"Saved media record for {index_entry.media_id}")
        return True

    def save_media_record(self, record: MediaRecord) -> bool:
        self.get_or_create_index_entry(record.media_item.id)
        with self._lock:
            media_id = record.media_item.id

            record_file = self._get_media_file_path(media_id)

            with AtomicWriter(record_file) as f:
                json.dump(record.model_dump(mode="json"), f, indent=2, default=str)

            logger.debug(f"Saved media record for {media_id}")
            return True

    def get_or_create_record(self, media_item: MediaItem) -> MediaRecord:
        record = self.get_media_record(media_item.id)
        if record is None:
            record = MediaRecord(media_item=media_item)
            self.save_media_record(record)
        else:
            record.media_item = media_item
            self.save_media_record(record)

        return record

    def update_media_index_entry(
        self,
        media_id: int,
        watched: bool = False,
        media_item: Optional[MediaItem] = None,
        progress: Optional[str] = None,
        status: Optional[UserMediaListStatus] = None,
        last_watch_position: Optional[str] = None,
        total_duration: Optional[str] = None,
        score: Optional[float] = None,
        repeat: Optional[int] = None,
        notes: Optional[str] = None,
        last_notified_episode: Optional[str] = None,
    ):
        """Update record from player feedback."""
        if media_item:
            self.get_or_create_record(media_item)

        index = self._load_index()
        index_entry = index.media_index[f"{self._media_api}_{media_id}"]

        if progress:
            index_entry.progress = progress
        if index_entry.status:
            if status:
                index_entry.status = status
        else:
            index_entry.status = UserMediaListStatus.WATCHING

        if last_watch_position:
            index_entry.last_watch_position = last_watch_position
        if total_duration:
            index_entry.total_duration = total_duration
        if score:
            index_entry.score = score
        if repeat:
            index_entry.repeat = repeat
        if notes:
            index_entry.notes = notes
        if last_notified_episode:
            index_entry.last_notified_episode = last_notified_episode

        if watched:
            index_entry.last_watched = datetime.now()

        index.media_index[f"{self._media_api}_{media_id}"] = index_entry
        self._save_index(index)

    # TODO: standardize params passed to this
    def get_recently_watched(self, limit: Optional[int] = None) -> MediaSearchResult:
        """Get recently watched anime."""
        index = self._load_index()

        sorted_entries = sorted(
            index.media_index.values(), key=lambda x: x.last_watched, reverse=True
        )

        recent_media: List[MediaItem] = []
        for entry in sorted_entries:
            record = self.get_media_record(entry.media_id)
            if record:
                recent_media.append(record.media_item)
            # if len(recent_media) == limit:
            #     break

        page_info = PageInfo(
            total=len(sorted_entries),
        )
        return MediaSearchResult(page_info=page_info, media=recent_media)

    def get_registry_stats(self) -> Dict:
        """Get comprehensive registry statistics."""
        try:
            index = self._load_index()

            return {
                "total_media_breakdown": index.media_count_breakdown,
                "status_breakdown": index.status_breakdown,
                "last_updated": index.last_updated.strftime("%Y-%m-%d %H:%M:%S"),
            }

        except Exception as e:
            logger.error(f"Failed to get registry stats: {e}")
            return {}

    def get_all_media_records(self) -> Generator[MediaRecord, None, List[MediaRecord]]:
        records = []
        for record_file in self.media_registry_dir.iterdir():
            try:
                if record_file.is_file():
                    id = record_file.stem
                    if record := self.get_media_record(int(id)):
                        records.append(record)
                        yield record
                else:
                    logger.warning(
                        f"{self.media_registry_dir} is impure; ignoring folder: {record_file}"
                    )
            except Exception as e:
                logger.warning(f"{self.media_registry_dir} is impure which caused: {e}")
        return records

    def search_for_media(self, params: MediaSearchParams) -> List[MediaItem]:
        """Search media by title."""
        try:
            # TODO: enhance performance
            media_items = [record.media_item for record in self.get_all_media_records()]

            return MediaFilter.apply(media_items, params)

        except Exception as e:
            logger.error(f"Failed to search media: {e}")
            return []

    def remove_media_record(self, media_id: int):
        with self._lock:
            record_file = self._get_media_file_path(media_id)
            if record_file.exists():
                record_file.unlink()
                try:
                    record_file.parent.rmdir()
                except OSError:
                    pass

        index = self._load_index()
        id = f"{self._media_api}_{media_id}"
        if id in index.media_index:
            del index.media_index[id]
            self._save_index(index)

            logger.debug(f"Removed media record {media_id}")

    def update_episode_download_status(
        self,
        media_id: int,
        episode_number: str,
        status: "DownloadStatus",
        file_path: Optional[Path] = None,
        file_size: Optional[int] = None,
        quality: Optional[str] = None,
        provider_name: Optional[str] = None,
        server_name: Optional[str] = None,
        subtitle_paths: Optional[list[Path]] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update the download status and metadata for a specific episode."""
        try:
            from .models import DownloadStatus, MediaEpisode
            
            record = self.get_media_record(media_id)
            if not record:
                logger.error(f"No media record found for ID {media_id}")
                return False
            
            # Find existing episode or create new one
            episode_record = None
            for episode in record.media_episodes:
                if episode.episode_number == episode_number:
                    episode_record = episode
                    break
            
            if not episode_record:
                if not file_path:
                    logger.error(f"File path required for new episode {episode_number}")
                    return False
                episode_record = MediaEpisode(
                    episode_number=episode_number,
                    file_path=file_path,
                    download_status=status,
                )
                record.media_episodes.append(episode_record)
            
            # Update episode metadata
            episode_record.download_status = status
            if file_path:
                episode_record.file_path = file_path
            if file_size is not None:
                episode_record.file_size = file_size
            if quality:
                episode_record.quality = quality
            if provider_name:
                episode_record.provider_name = provider_name
            if server_name:
                episode_record.server_name = server_name
            if subtitle_paths:
                episode_record.subtitle_paths = subtitle_paths
            if error_message:
                episode_record.last_error = error_message
            
            # Increment download attempts if this is a failure
            if status == DownloadStatus.FAILED:
                episode_record.download_attempts += 1
            
            # Save the updated record
            return self.save_media_record(record)
            
        except Exception as e:
            logger.error(f"Failed to update episode download status: {e}")
            return False

    def get_episodes_by_download_status(
        self, status: "DownloadStatus"
    ) -> list[tuple[int, str]]:
        """Get all episodes with a specific download status."""
        try:
            from .models import DownloadStatus
            
            episodes = []
            for record in self.get_all_media_records():
                for episode in record.media_episodes:
                    if episode.download_status == status:
                        episodes.append((record.media_item.id, episode.episode_number))
            return episodes
            
        except Exception as e:
            logger.error(f"Failed to get episodes by status: {e}")
            return []

    def get_download_statistics(self) -> dict:
        """Get comprehensive download statistics."""
        try:
            from .models import DownloadStatus
            
            stats = {
                "total_episodes": 0,
                "downloaded": 0,
                "failed": 0,
                "queued": 0,
                "downloading": 0,
                "paused": 0,
                "total_size_bytes": 0,
                "by_quality": {},
                "by_provider": {},
            }
            
            for record in self.get_all_media_records():
                for episode in record.media_episodes:
                    stats["total_episodes"] += 1
                    
                    # Count by status
                    status_key = episode.download_status.value.lower()
                    if status_key == "completed":
                        stats["downloaded"] += 1
                    elif status_key == "failed":
                        stats["failed"] += 1
                    elif status_key == "queued":
                        stats["queued"] += 1
                    elif status_key == "downloading":
                        stats["downloading"] += 1
                    elif status_key == "paused":
                        stats["paused"] += 1
                    
                    # Aggregate file sizes
                    if episode.file_size:
                        stats["total_size_bytes"] += episode.file_size
                    
                    # Count by quality
                    if episode.quality:
                        stats["by_quality"][episode.quality] = (
                            stats["by_quality"].get(episode.quality, 0) + 1
                        )
                    
                    # Count by provider
                    if episode.provider_name:
                        stats["by_provider"][episode.provider_name] = (
                            stats["by_provider"].get(episode.provider_name, 0) + 1
                        )
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get download statistics: {e}")
            return {}
