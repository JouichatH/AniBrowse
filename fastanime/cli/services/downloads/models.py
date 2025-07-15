"""
Pydantic models for download tracking system.

This module defines the data models used throughout the download tracking system,
providing type safety and validation using Pydantic v2.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from ....core.constants import APP_DATA_DIR
from ....libs.api.types import MediaItem

logger = logging.getLogger(__name__)

# Type aliases for better readability
DownloadStatus = Literal["completed", "failed", "downloading", "queued", "paused"]
QualityOption = Literal["360", "480", "720", "1080", "best"]
MediaStatus = Literal["active", "completed", "paused", "failed"]


class EpisodeDownload(BaseModel):
    """
    Pydantic model for individual episode download tracking.
    
    Tracks all information related to a single episode download including
    file location, download progress, quality, and integrity information.
    """
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=True,  # Immutable after creation for data integrity
    )
    
    episode_number: int = Field(gt=0, description="Episode number")
    file_path: Path = Field(description="Path to downloaded file")
    file_size: int = Field(ge=0, description="File size in bytes")
    download_date: datetime = Field(default_factory=datetime.now)
    quality: QualityOption = Field(default="1080")
    source_provider: str = Field(description="Provider used for download")
    status: DownloadStatus = Field(default="queued")
    checksum: Optional[str] = Field(None, description="SHA256 checksum for integrity")
    subtitle_files: List[Path] = Field(default_factory=list)
    download_progress: float = Field(default=0.0, ge=0.0, le=1.0)
    error_message: Optional[str] = Field(None, description="Error message if failed")
    download_speed: Optional[float] = Field(None, description="Download speed in bytes/sec")
    
    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: Path) -> Path:
        """Ensure file path is absolute and within allowed directories."""
        if not v.is_absolute():
            raise ValueError("File path must be absolute")
        return v
    
    @computed_field
    @property
    def is_completed(self) -> bool:
        """Check if download is completed and file exists."""
        return self.status == "completed" and self.file_path.exists()
    
    @computed_field
    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes."""
        return self.file_size / (1024 * 1024)
    
    @computed_field
    @property
    def display_status(self) -> str:
        """Get human-readable status."""
        status_map = {
            "completed": "✓ Completed",
            "failed": "✗ Failed",
            "downloading": "⬇ Downloading",
            "queued": "⏳ Queued",
            "paused": "⏸ Paused"
        }
        return status_map.get(self.status, self.status)
    
    def generate_checksum(self) -> Optional[str]:
        """Generate SHA256 checksum for the downloaded file."""
        if not self.file_path.exists():
            return None
        
        try:
            sha256_hash = hashlib.sha256()
            with open(self.file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Failed to generate checksum for {self.file_path}: {e}")
            return None
    
    def verify_integrity(self) -> bool:
        """Verify file integrity using stored checksum."""
        if not self.checksum or not self.file_path.exists():
            return False
        
        current_checksum = self.generate_checksum()
        return current_checksum == self.checksum


class MediaDownloadRecord(BaseModel):
    """
    Pydantic model for anime series download tracking.
    
    Manages download information for an entire anime series including
    individual episodes, metadata, and organization preferences.
    """
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )
    
    media_item: MediaItem = Field(description="The anime media item")
    episodes: Dict[int, EpisodeDownload] = Field(default_factory=dict)
    download_path: Path = Field(description="Base download directory for this anime")
    created_date: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    preferred_quality: QualityOption = Field(default="1080")
    auto_download_new: bool = Field(default=False, description="Auto-download new episodes")
    tags: List[str] = Field(default_factory=list, description="User-defined tags")
    notes: Optional[str] = Field(None, description="User notes")
    
    # Organization preferences
    naming_template: str = Field(
        default="{title}/Season {season:02d}/{episode:02d} - {episode_title}.{ext}",
        description="File naming template"
    )
    
    @field_validator("download_path")
    @classmethod
    def validate_download_path(cls, v: Path) -> Path:
        """Ensure download path is absolute."""
        if not v.is_absolute():
            raise ValueError("Download path must be absolute")
        return v
    
    @computed_field
    @property
    def total_episodes_downloaded(self) -> int:
        """Get count of successfully downloaded episodes."""
        return len([ep for ep in self.episodes.values() if ep.is_completed])
    
    @computed_field
    @property
    def total_size_bytes(self) -> int:
        """Get total size of all downloaded episodes in bytes."""
        return sum(ep.file_size for ep in self.episodes.values() if ep.is_completed)
    
    @computed_field
    @property
    def total_size_gb(self) -> float:
        """Get total size in gigabytes."""
        return self.total_size_bytes / (1024 * 1024 * 1024)
    
    @computed_field
    @property
    def completion_percentage(self) -> float:
        """Get completion percentage based on total episodes."""
        if not self.media_item.episodes or self.media_item.episodes == 0:
            return 0.0
        return (self.total_episodes_downloaded / self.media_item.episodes) * 100
    
    @computed_field
    @property
    def display_title(self) -> str:
        """Get display title for the anime."""
        return (
            self.media_item.title.english
            or self.media_item.title.romaji
            or f"Anime {self.media_item.id}"
        )
    
    @computed_field
    @property
    def status(self) -> MediaStatus:
        """Determine overall download status for this anime."""
        if not self.episodes:
            return "active"
        
        statuses = [ep.status for ep in self.episodes.values()]
        
        if all(s == "completed" for s in statuses):
            if self.media_item.episodes and len(self.episodes) >= self.media_item.episodes:
                return "completed"
        
        if any(s == "failed" for s in statuses):
            return "failed"
        
        if any(s in ["downloading", "queued"] for s in statuses):
            return "active"
        
        return "paused"
    
    def get_next_episode_to_download(self) -> Optional[int]:
        """Get the next episode number that should be downloaded."""
        if not self.media_item.episodes:
            return None
        
        downloaded_episodes = set(ep.episode_number for ep in self.episodes.values() if ep.is_completed)
        
        for episode_num in range(1, self.media_item.episodes + 1):
            if episode_num not in downloaded_episodes:
                return episode_num
        
        return None
    
    def get_failed_episodes(self) -> List[int]:
        """Get list of episode numbers that failed to download."""
        return [
            ep.episode_number for ep in self.episodes.values()
            if ep.status == "failed"
        ]
    
    def update_last_modified(self) -> None:
        """Update the last_updated timestamp."""
        # Create a new instance with updated timestamp since the model might be frozen
        object.__setattr__(self, "last_updated", datetime.now())


class MediaIndexEntry(BaseModel):
    """
    Lightweight entry in the download index for fast operations.
    
    Provides quick access to basic information about a download record
    without loading the full MediaDownloadRecord.
    """
    
    model_config = ConfigDict(validate_assignment=True)
    
    media_id: int = Field(description="AniList media ID")
    title: str = Field(description="Display title")
    episode_count: int = Field(default=0, ge=0)
    completed_episodes: int = Field(default=0, ge=0)
    last_download: Optional[datetime] = None
    status: MediaStatus = Field(default="active")
    total_size: int = Field(default=0, ge=0)
    file_path: Path = Field(description="Path to the media record file")
    
    @computed_field
    @property
    def completion_percentage(self) -> float:
        """Get completion percentage."""
        if self.episode_count == 0:
            return 0.0
        return (self.completed_episodes / self.episode_count) * 100
    
    @computed_field
    @property
    def total_size_mb(self) -> float:
        """Get total size in megabytes."""
        return self.total_size / (1024 * 1024)


class DownloadIndex(BaseModel):
    """
    Lightweight index for fast download operations.
    
    Maintains an overview of all download records without loading
    the full data, enabling fast searches and filtering.
    """
    
    model_config = ConfigDict(validate_assignment=True)
    
    version: str = Field(default="1.0")
    last_updated: datetime = Field(default_factory=datetime.now)
    media_count: int = Field(default=0, ge=0)
    total_episodes: int = Field(default=0, ge=0)
    total_size_bytes: int = Field(default=0, ge=0)
    media_index: Dict[int, MediaIndexEntry] = Field(default_factory=dict)
    
    @computed_field
    @property
    def total_size_gb(self) -> float:
        """Get total size across all downloads in gigabytes."""
        return self.total_size_bytes / (1024 * 1024 * 1024)
    
    @computed_field
    @property
    def completion_stats(self) -> Dict[str, int]:
        """Get completion statistics."""
        stats = {"completed": 0, "active": 0, "failed": 0, "paused": 0}
        for entry in self.media_index.values():
            stats[entry.status] = stats.get(entry.status, 0) + 1
        return stats
    
    def add_media_entry(self, media_record: MediaDownloadRecord) -> None:
        """Add or update a media entry in the index."""
        entry = MediaIndexEntry(
            media_id=media_record.media_item.id,
            title=media_record.display_title,
            episode_count=media_record.media_item.episodes or 0,
            completed_episodes=media_record.total_episodes_downloaded,
            last_download=media_record.last_updated,
            status=media_record.status,
            total_size=media_record.total_size_bytes,
            file_path=APP_DATA_DIR / "downloads" / "media" / f"{media_record.media_item.id}.json"
        )
        
        self.media_index[media_record.media_item.id] = entry
        self.media_count = len(self.media_index)
        self.total_episodes = sum(entry.completed_episodes for entry in self.media_index.values())
        self.total_size_bytes = sum(entry.total_size for entry in self.media_index.values())
        self.last_updated = datetime.now()
    
    def remove_media_entry(self, media_id: int) -> bool:
        """Remove a media entry from the index."""
        if media_id in self.media_index:
            del self.media_index[media_id]
            self.media_count = len(self.media_index)
            self.total_episodes = sum(entry.completed_episodes for entry in self.media_index.values())
            self.total_size_bytes = sum(entry.total_size for entry in self.media_index.values())
            self.last_updated = datetime.now()
            return True
        return False


class DownloadQueueItem(BaseModel):
    """
    Item in the download queue.
    
    Represents a single episode queued for download with priority
    and scheduling information.
    """
    
    model_config = ConfigDict(frozen=True)
    
    media_id: int
    episode_number: int
    priority: int = Field(default=0, description="Higher number = higher priority")
    added_date: datetime = Field(default_factory=datetime.now)
    estimated_size: Optional[int] = Field(None, description="Estimated file size")
    quality_preference: QualityOption = Field(default="1080")
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, gt=0)
    
    @computed_field
    @property
    def can_retry(self) -> bool:
        """Check if this item can be retried."""
        return self.retry_count < self.max_retries
    
    @computed_field
    @property
    def estimated_size_mb(self) -> Optional[float]:
        """Get estimated size in megabytes."""
        if self.estimated_size is None:
            return None
        return self.estimated_size / (1024 * 1024)


class DownloadQueue(BaseModel):
    """
    Download queue management.
    
    Manages the queue of episodes waiting to be downloaded with
    priority handling and scheduling.
    """
    
    model_config = ConfigDict(validate_assignment=True)
    
    items: List[DownloadQueueItem] = Field(default_factory=list)
    max_size: int = Field(default=100, gt=0)
    last_updated: datetime = Field(default_factory=datetime.now)
    
    def add_item(self, item: DownloadQueueItem) -> bool:
        """Add an item to the queue."""
        if len(self.items) >= self.max_size:
            return False
        
        # Check for duplicates
        for existing_item in self.items:
            if (existing_item.media_id == item.media_id and 
                existing_item.episode_number == item.episode_number):
                return False
        
        self.items.append(item)
        # Sort by priority (highest first), then by added date
        self.items.sort(key=lambda x: (-x.priority, x.added_date))
        self.last_updated = datetime.now()
        return True
    
    def get_next_item(self) -> Optional[DownloadQueueItem]:
        """Get the next item to download."""
        if not self.items:
            return None
        return self.items[0]
    
    def remove_item(self, media_id: int, episode_number: int) -> bool:
        """Remove an item from the queue."""
        for i, item in enumerate(self.items):
            if item.media_id == media_id and item.episode_number == episode_number:
                del self.items[i]
                self.last_updated = datetime.now()
                return True
        return False
    
    def clear(self) -> None:
        """Clear all items from the queue."""
        self.items.clear()
        self.last_updated = datetime.now()
    
    @computed_field
    @property
    def total_estimated_size(self) -> int:
        """Get total estimated size of all queued items."""
        return sum(item.estimated_size or 0 for item in self.items)
