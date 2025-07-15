"""
Unified Media Registry Manager.

Provides centralized management of anime metadata, downloads, and watch history
through a single interface, eliminating data duplication.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional

from ....core.constants import APP_DATA_DIR
from ....libs.api.types import MediaItem
from .models import MediaRecord, MediaRegistryIndex, EpisodeStatus, UserMediaData

logger = logging.getLogger(__name__)


class MediaRegistryManager:
    """
    Unified manager for anime data, downloads, and watch history.
    
    Provides a single interface for all media-related operations,
    eliminating duplication between download and watch systems.
    """
    
    def __init__(self, registry_path: Path = None):
        self.registry_path = registry_path or APP_DATA_DIR / "media_registry"
        self.media_dir = self.registry_path / "media"
        self.cache_dir = self.registry_path / "cache"
        self.index_file = self.registry_path / "index.json"
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Cached data
        self._index: Optional[MediaRegistryIndex] = None
        self._loaded_records: Dict[int, MediaRecord] = {}
        
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Ensure registry directories exist."""
        try:
            self.registry_path.mkdir(parents=True, exist_ok=True)
            self.media_dir.mkdir(exist_ok=True)
            self.cache_dir.mkdir(exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create registry directories: {e}")
    
    def _load_index(self) -> MediaRegistryIndex:
        """Load or create the registry index."""
        if self._index is not None:
            return self._index
        
        try:
            if self.index_file.exists():
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._index = MediaRegistryIndex.model_validate(data)
            else:
                self._index = MediaRegistryIndex()
                self._save_index()
            
            logger.debug(f"Loaded registry index with {self._index.media_count} entries")
            return self._index
            
        except Exception as e:
            logger.error(f"Failed to load registry index: {e}")
            self._index = MediaRegistryIndex()
            return self._index
    
    def _save_index(self) -> bool:
        """Save the registry index."""
        try:
            # Atomic write
            temp_file = self.index_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self._index.model_dump(), f, indent=2, ensure_ascii=False, default=str)
            
            temp_file.replace(self.index_file)
            logger.debug("Saved registry index")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save registry index: {e}")
            return False
    
    def _get_media_file_path(self, media_id: int) -> Path:
        """Get file path for media record."""
        return self.media_dir / str(media_id) / "record.json"
    
    def get_media_record(self, media_id: int) -> Optional[MediaRecord]:
        """Get media record by ID."""
        with self._lock:
            # Check cache first
            if media_id in self._loaded_records:
                return self._loaded_records[media_id]
            
            try:
                record_file = self._get_media_file_path(media_id)
                if not record_file.exists():
                    return None
                
                with open(record_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                record = MediaRecord.model_validate(data)
                self._loaded_records[media_id] = record
                
                logger.debug(f"Loaded media record for {media_id}")
                return record
                
            except Exception as e:
                logger.error(f"Failed to load media record {media_id}: {e}")
                return None
    
    def save_media_record(self, record: MediaRecord) -> bool:
        """Save media record to storage."""
        with self._lock:
            try:
                media_id = record.media_item.id
                record_file = self._get_media_file_path(media_id)
                
                # Ensure directory exists
                record_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Atomic write
                temp_file = record_file.with_suffix('.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(record.model_dump(), f, indent=2, ensure_ascii=False, default=str)
                
                temp_file.replace(record_file)
                
                # Update cache and index
                self._loaded_records[media_id] = record
                index = self._load_index()
                index.add_media_entry(record)
                self._save_index()
                
                logger.debug(f"Saved media record for {media_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to save media record: {e}")
                return False
    
    def get_or_create_record(self, media_item: MediaItem) -> MediaRecord:
        """Get existing record or create new one."""
        record = self.get_media_record(media_item.id)
        if record is None:
            record = MediaRecord(media_item=media_item)
            self.save_media_record(record)
        else:
            # Update media_item in case metadata changed
            record.media_item = media_item
            record.user_data.update_timestamp()
            self.save_media_record(record)
        
        return record
    
    def update_download_completion(self, media_item: MediaItem, episode_number: int, 
                                 file_path: Path, file_size: int, quality: str, 
                                 checksum: Optional[str] = None) -> bool:
        """Update record when download completes."""
        try:
            record = self.get_or_create_record(media_item)
            record.update_from_download_completion(
                episode_number, file_path, file_size, quality, checksum
            )
            return self.save_media_record(record)
            
        except Exception as e:
            logger.error(f"Failed to update download completion: {e}")
            return False
    
    def update_from_player_result(self, media_item: MediaItem, episode_number: int, 
                                stop_time: str, total_time: str) -> bool:
        """Update record from player feedback."""
        try:
            record = self.get_or_create_record(media_item)
            record.update_from_player_result(episode_number, stop_time, total_time)
            return self.save_media_record(record)
            
        except Exception as e:
            logger.error(f"Failed to update from player result: {e}")
            return False
    
    def mark_episode_watched(self, media_id: int, episode_number: int, 
                           progress: float = 1.0) -> bool:
        """Mark episode as watched."""
        try:
            record = self.get_media_record(media_id)
            if not record:
                return False
            
            episode = record.get_episode_status(episode_number)
            episode.watch_status = "completed" if progress >= 0.8 else "watching"
            episode.watch_progress = progress
            episode.watch_date = datetime.now()
            episode.watch_count += 1
            
            record.user_data.update_timestamp()
            return self.save_media_record(record)
            
        except Exception as e:
            logger.error(f"Failed to mark episode watched: {e}")
            return False
    
    def get_currently_watching(self) -> List[MediaRecord]:
        """Get anime currently being watched."""
        try:
            index = self._load_index()
            watching_records = []
            
            for entry in index.media_index.values():
                if entry.user_status == "watching":
                    record = self.get_media_record(entry.media_id)
                    if record:
                        watching_records.append(record)
            
            return watching_records
            
        except Exception as e:
            logger.error(f"Failed to get currently watching: {e}")
            return []
    
    def get_recently_watched(self, limit: int = 10) -> List[MediaRecord]:
        """Get recently watched anime."""
        try:
            index = self._load_index()
            
            # Sort by last updated
            sorted_entries = sorted(
                index.media_index.values(),
                key=lambda x: x.last_updated,
                reverse=True
            )
            
            recent_records = []
            for entry in sorted_entries[:limit]:
                if entry.episodes_watched > 0:  # Only include if actually watched
                    record = self.get_media_record(entry.media_id)
                    if record:
                        recent_records.append(record)
            
            return recent_records
            
        except Exception as e:
            logger.error(f"Failed to get recently watched: {e}")
            return []
    
    def get_download_queue_candidates(self) -> List[MediaRecord]:
        """Get anime that have downloads queued or in progress."""
        try:
            index = self._load_index()
            download_records = []
            
            for entry in index.media_index.values():
                if entry.episodes_downloaded < entry.total_episodes:
                    record = self.get_media_record(entry.media_id)
                    if record:
                        # Check if any episodes are queued/downloading
                        has_active_downloads = any(
                            ep.download_status in ["queued", "downloading"]
                            for ep in record.episodes.values()
                        )
                        if has_active_downloads:
                            download_records.append(record)
            
            return download_records
            
        except Exception as e:
            logger.error(f"Failed to get download queue candidates: {e}")
            return []
    
    def get_continue_episode(self, media_id: int, available_episodes: List[str]) -> Optional[str]:
        """Get episode to continue from based on watch history."""
        try:
            record = self.get_media_record(media_id)
            if not record:
                return None
            
            next_episode = record.next_episode_to_watch
            if next_episode and str(next_episode) in available_episodes:
                return str(next_episode)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get continue episode: {e}")
            return None
    
    def get_registry_stats(self) -> Dict:
        """Get comprehensive registry statistics."""
        try:
            index = self._load_index()
            
            total_downloaded = sum(entry.episodes_downloaded for entry in index.media_index.values())
            total_watched = sum(entry.episodes_watched for entry in index.media_index.values())
            
            return {
                "total_anime": index.media_count,
                "status_breakdown": index.status_breakdown,
                "total_episodes_downloaded": total_downloaded,
                "total_episodes_watched": total_watched,
                "last_updated": index.last_updated.strftime("%Y-%m-%d %H:%M:%S"),
            }
            
        except Exception as e:
            logger.error(f"Failed to get registry stats: {e}")
            return {}
    
    def search_media(self, query: str) -> List[MediaRecord]:
        """Search media by title."""
        try:
            index = self._load_index()
            query_lower = query.lower()
            results = []
            
            for entry in index.media_index.values():
                if query_lower in entry.title.lower():
                    record = self.get_media_record(entry.media_id)
                    if record:
                        results.append(record)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search media: {e}")
            return []
    
    def remove_media_record(self, media_id: int) -> bool:
        """Remove media record completely."""
        with self._lock:
            try:
                # Remove from cache
                if media_id in self._loaded_records:
                    del self._loaded_records[media_id]
                
                # Remove file
                record_file = self._get_media_file_path(media_id)
                if record_file.exists():
                    record_file.unlink()
                    
                    # Remove directory if empty
                    try:
                        record_file.parent.rmdir()
                    except OSError:
                        pass  # Directory not empty
                
                # Update index
                index = self._load_index()
                if media_id in index.media_index:
                    del index.media_index[media_id]
                    index.media_count = len(index.media_index)
                    self._save_index()
                
                logger.debug(f"Removed media record {media_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to remove media record {media_id}: {e}")
                return False


# Global instance
_media_registry: Optional[MediaRegistryManager] = None


def get_media_registry() -> MediaRegistryManager:
    """Get or create the global media registry instance."""
    global _media_registry
    if _media_registry is None:
        _media_registry = MediaRegistryManager()
    return _media_registry
