import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List, Optional

from ....core.config.model import MediaRegistryConfig
from ....core.utils.file import AtomicWriter, FileLock, check_file_modified
from ....libs.api.params import ApiSearchParams
from ....libs.api.types import MediaItem
from ....libs.players.types import PlayerResult
from .filters import MediaFilter
from .models import (
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

        logger.debug(f"Loaded registry index with {self._index.media_count} entries")
        return self._index

    def _save_index(self, index: MediaRegistryIndex):
        """Save the registry index."""
        with self._lock:
            index.last_updated = datetime.now()
            with AtomicWriter(self._index_file) as f:
                json.dump(index.model_dump(), f, indent=2)

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
        with self._lock:
            index = self._load_index()
            index.media_index[f"{self._media_api}_{index_entry.media_id}"] = index_entry
            self._save_index(index)

            logger.debug(f"Saved media record for {index_entry.media_id}")
            return True

    def save_media_record(self, record: MediaRecord) -> bool:
        with self._lock:
            self.get_or_create_index_entry(record.media_item.id)
            media_id = record.media_item.id

            record_file = self._get_media_file_path(media_id)

            with AtomicWriter(record_file) as f:
                json.dump(record.model_dump(), f, indent=2, default=str)

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

    def update_from_player_result(
        self, media_item: MediaItem, episode_number: str, player_result: PlayerResult
    ):
        """Update record from player feedback."""
        self.get_or_create_record(media_item)

        index = self._load_index()
        index_entry = index.media_index[f"{self._media_api}_{media_item.id}"]

        index_entry.last_watch_position = player_result.stop_time
        index_entry.total_duration = player_result.total_time
        index_entry.progress = episode_number
        index_entry.last_watched = datetime.now()

        index.media_index[f"{self._media_api}_{media_item.id}"] = index_entry
        self._save_index(index)

    def get_recently_watched(self, limit: int) -> List[MediaRecord]:
        """Get recently watched anime."""
        index = self._load_index()

        sorted_entries = sorted(
            index.media_index.values(), key=lambda x: x.last_watched, reverse=True
        )

        recent_media = []
        for entry in sorted_entries:
            record = self.get_media_record(entry.media_id)
            if record:
                recent_media.append(record.media_item)
            if len(recent_media) == limit:
                break

        return recent_media

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

    def search_for_media(self, params: ApiSearchParams) -> List[MediaItem]:
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
