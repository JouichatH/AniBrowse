"""
Unified data models for Media Registry.

Provides single source of truth for anime metadata, episode tracking,
and user data, eliminating duplication between download and watch systems.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

from ....libs.api.types import MediaItem

logger = logging.getLogger(__name__)

# Type aliases
DownloadStatus = Literal["not_downloaded", "queued", "downloading", "completed", "failed", "paused"]
WatchStatus = Literal["not_watched", "watching", "completed", "dropped", "paused"]
MediaUserStatus = Literal["planning", "watching", "completed", "dropped", "paused"]


class EpisodeStatus(BaseModel):
    """
    Unified episode status tracking both download and watch state.
    Single source of truth for episode-level data.
    """
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )
    
    episode_number: int = Field(gt=0)
    
    # Download tracking
    download_status: DownloadStatus = "not_downloaded"
    file_path: Optional[Path] = None
    file_size: Optional[int] = None
    download_date: Optional[datetime] = None
    download_quality: Optional[str] = None
    checksum: Optional[str] = None
    
    # Watch tracking (from player feedback)
    watch_status: WatchStatus = "not_watched"
    watch_progress: float = Field(default=0.0, ge=0.0, le=1.0)
    last_watch_position: Optional[str] = None  # "HH:MM:SS" from PlayerResult
    total_duration: Optional[str] = None  # "HH:MM:SS" from PlayerResult
    watch_date: Optional[datetime] = None
    watch_count: int = Field(default=0, ge=0)
    
    # Integration fields
    auto_marked_watched: bool = Field(default=False, description="Auto-marked watched from download")
    
    @computed_field
    @property
    def is_available_locally(self) -> bool:
        """Check if episode is downloaded and file exists."""
        return (
            self.download_status == "completed" 
            and self.file_path is not None 
            and self.file_path.exists()
        )
    
    @computed_field  
    @property
    def completion_percentage(self) -> float:
        """Calculate actual watch completion from player data."""
        if self.last_watch_position and self.total_duration:
            try:
                last_seconds = self._time_to_seconds(self.last_watch_position)
                total_seconds = self._time_to_seconds(self.total_duration)
                if total_seconds > 0:
                    return min(100.0, (last_seconds / total_seconds) * 100)
            except (ValueError, AttributeError):
                pass
        return self.watch_progress * 100
    
    @computed_field
    @property
    def should_auto_mark_watched(self) -> bool:
        """Check if episode should be auto-marked as watched."""
        return self.completion_percentage >= 80.0 and self.watch_status != "completed"
    
    def _time_to_seconds(self, time_str: str) -> int:
        """Convert HH:MM:SS to seconds."""
        try:
            parts = time_str.split(':')
            if len(parts) == 3:
                h, m, s = map(int, parts)
                return h * 3600 + m * 60 + s
        except (ValueError, AttributeError):
            pass
        return 0
    
    def update_from_player_result(self, stop_time: str, total_time: str) -> None:
        """Update watch status from PlayerResult."""
        self.last_watch_position = stop_time
        self.total_duration = total_time
        self.watch_date = datetime.now()
        self.watch_count += 1
        
        # Auto-mark as completed if 80%+ watched
        if self.should_auto_mark_watched:
            self.watch_status = "completed"
            self.watch_progress = 1.0


class UserMediaData(BaseModel):
    """
    User-specific data for a media item.
    Consolidates user preferences from both download and watch systems.
    """
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )
    
    # User status and preferences
    status: MediaUserStatus = "planning"
    notes: str = ""
    tags: List[str] = Field(default_factory=list)
    rating: Optional[int] = Field(None, ge=1, le=10)
    favorite: bool = False
    priority: int = Field(default=0, ge=0)
    
    # Download preferences
    preferred_quality: str = "1080"
    auto_download_new: bool = False
    download_path: Optional[Path] = None
    
    # Watch preferences  
    continue_from_history: bool = True
    auto_mark_watched_on_download: bool = False
    
    # Timestamps
    created_date: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    
    def update_timestamp(self) -> None:
        """Update last_updated timestamp."""
        self.last_updated = datetime.now()


class MediaRecord(BaseModel):
    """
    Unified media record - single source of truth for anime data.
    Replaces both MediaDownloadRecord and WatchHistoryEntry.
    """
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )
    
    media_item: MediaItem
    episodes: Dict[int, EpisodeStatus] = Field(default_factory=dict)
    user_data: UserMediaData = Field(default_factory=UserMediaData)
    
    @computed_field
    @property
    def display_title(self) -> str:
        """Get display title for the anime."""
        return (
            self.media_item.title.english
            or self.media_item.title.romaji
            or self.media_item.title.native
            or f"Anime #{self.media_item.id}"
        )
    
    @computed_field
    @property
    def total_episodes_downloaded(self) -> int:
        """Count of successfully downloaded episodes."""
        return len([ep for ep in self.episodes.values() if ep.is_available_locally])
    
    @computed_field
    @property
    def total_episodes_watched(self) -> int:
        """Count of completed episodes."""
        return len([ep for ep in self.episodes.values() if ep.watch_status == "completed"])
    
    @computed_field
    @property
    def last_watched_episode(self) -> int:
        """Get highest watched episode number."""
        watched_episodes = [
            ep.episode_number for ep in self.episodes.values() 
            if ep.watch_status == "completed"
        ]
        return max(watched_episodes) if watched_episodes else 0
    
    @computed_field
    @property
    def next_episode_to_watch(self) -> Optional[int]:
        """Get next episode to watch based on progress."""
        if not self.episodes:
            return 1
        
        # Find highest completed episode
        last_watched = self.last_watched_episode
        
        if last_watched == 0:
            return 1
        
        next_ep = last_watched + 1
        total_eps = self.media_item.episodes or float('inf')
        
        return next_ep if next_ep <= total_eps else None
    
    @computed_field
    @property
    def download_completion_percentage(self) -> float:
        """Download completion percentage."""
        if not self.media_item.episodes or self.media_item.episodes == 0:
            return 0.0
        return (self.total_episodes_downloaded / self.media_item.episodes) * 100
    
    @computed_field
    @property
    def watch_completion_percentage(self) -> float:
        """Watch completion percentage.""" 
        if not self.media_item.episodes or self.media_item.episodes == 0:
            return 0.0
        return (self.total_episodes_watched / self.media_item.episodes) * 100
    
    def get_episode_status(self, episode_number: int) -> EpisodeStatus:
        """Get or create episode status."""
        if episode_number not in self.episodes:
            self.episodes[episode_number] = EpisodeStatus(episode_number=episode_number)
        return self.episodes[episode_number]
    
    def update_from_download_completion(self, episode_number: int, file_path: Path, 
                                      file_size: int, quality: str, checksum: Optional[str] = None) -> None:
        """Update episode status when download completes."""
        episode = self.get_episode_status(episode_number)
        episode.download_status = "completed"
        episode.file_path = file_path
        episode.file_size = file_size
        episode.download_quality = quality
        episode.checksum = checksum
        episode.download_date = datetime.now()
        
        # Auto-mark as watched if enabled
        if self.user_data.auto_mark_watched_on_download and episode.watch_status == "not_watched":
            episode.watch_status = "completed"
            episode.watch_progress = 1.0
            episode.auto_marked_watched = True
            episode.watch_date = datetime.now()
        
        self.user_data.update_timestamp()
    
    def update_from_player_result(self, episode_number: int, stop_time: str, total_time: str) -> None:
        """Update episode status from player feedback."""
        episode = self.get_episode_status(episode_number)
        episode.update_from_player_result(stop_time, total_time)
        self.user_data.update_timestamp()
        
        # Update overall status based on progress
        if episode.watch_status == "completed":
            if self.user_data.status == "planning":
                self.user_data.status = "watching"
            
            # Check if anime is completed
            if self.media_item.episodes and self.total_episodes_watched >= self.media_item.episodes:
                self.user_data.status = "completed"


class MediaRegistryIndex(BaseModel):
    """
    Lightweight index for fast media registry operations.
    Provides quick access without loading full MediaRecord files.
    """
    
    model_config = ConfigDict(validate_assignment=True)
    
    version: str = Field(default="1.0")
    last_updated: datetime = Field(default_factory=datetime.now)
    media_count: int = Field(default=0, ge=0)
    
    # Quick access index
    media_index: Dict[int, "MediaIndexEntry"] = Field(default_factory=dict)
    
    @computed_field
    @property
    def status_breakdown(self) -> Dict[str, int]:
        """Get breakdown by user status."""
        breakdown = {"planning": 0, "watching": 0, "completed": 0, "dropped": 0, "paused": 0}
        for entry in self.media_index.values():
            breakdown[entry.user_status] = breakdown.get(entry.user_status, 0) + 1
        return breakdown
    
    def add_media_entry(self, media_record: MediaRecord) -> None:
        """Add or update media entry in index."""
        entry = MediaIndexEntry(
            media_id=media_record.media_item.id,
            title=media_record.display_title,
            user_status=media_record.user_data.status,
            episodes_downloaded=media_record.total_episodes_downloaded,
            episodes_watched=media_record.total_episodes_watched,
            total_episodes=media_record.media_item.episodes or 0,
            last_updated=media_record.user_data.last_updated,
            last_watched_episode=media_record.last_watched_episode,
            next_episode=media_record.next_episode_to_watch
        )
        
        self.media_index[media_record.media_item.id] = entry
        self.media_count = len(self.media_index)
        self.last_updated = datetime.now()


class MediaIndexEntry(BaseModel):
    """Lightweight index entry for a media item."""
    
    model_config = ConfigDict(validate_assignment=True)
    
    media_id: int
    title: str
    user_status: MediaUserStatus
    episodes_downloaded: int = 0
    episodes_watched: int = 0
    total_episodes: int = 0
    last_updated: datetime
    last_watched_episode: int = 0
    next_episode: Optional[int] = None
    
    @computed_field
    @property
    def download_progress(self) -> float:
        """Download progress percentage."""
        if self.total_episodes == 0:
            return 0.0
        return (self.episodes_downloaded / self.total_episodes) * 100
    
    @computed_field
    @property
    def watch_progress(self) -> float:
        """Watch progress percentage."""
        if self.total_episodes == 0:
            return 0.0
        return (self.episodes_watched / self.total_episodes) * 100
