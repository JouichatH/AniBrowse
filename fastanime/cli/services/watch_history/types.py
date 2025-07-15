"""
Watch history data models and types for the interactive CLI.
Provides comprehensive data structures for tracking and managing local watch history.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from ....libs.api.types import MediaItem

logger = logging.getLogger(__name__)


class WatchHistoryEntry(BaseModel):
    """
    Represents a single entry in the watch history.
    Contains media information and viewing progress.
    """
    
    media_item: MediaItem
    last_watched_episode: int = 0
    watch_progress: float = 0.0  # Progress within the episode (0.0-1.0)
    times_watched: int = 1
    first_watched: datetime = Field(default_factory=datetime.now)
    last_watched: datetime = Field(default_factory=datetime.now)
    status: str = "watching"  # watching, completed, dropped, paused
    notes: str = ""
    
    # Download integration fields
    has_downloads: bool = Field(default=False, description="Whether episodes are downloaded")
    offline_available: bool = Field(default=False, description="Can watch offline")
    
    # With Pydantic, serialization is automatic!
    # No need for manual to_dict() and from_dict() methods
    # Use: entry.model_dump() and WatchHistoryEntry.model_validate(data)
    
    def update_progress(self, episode: int, progress: float = 0.0, status: Optional[str] = None):
        """Update watch progress for this entry."""
        self.last_watched_episode = max(self.last_watched_episode, episode)
        self.watch_progress = progress
        self.last_watched = datetime.now()
        if status:
            self.status = status
    
    def mark_completed(self):
        """Mark this entry as completed."""
        self.status = "completed"
        self.last_watched = datetime.now()
        if self.media_item.episodes:
            self.last_watched_episode = self.media_item.episodes
        self.watch_progress = 1.0
    
    def get_display_title(self) -> str:
        """Get the best available title for display."""
        if self.media_item.title.english:
            return self.media_item.title.english
        elif self.media_item.title.romaji:
            return self.media_item.title.romaji
        elif self.media_item.title.native:
            return self.media_item.title.native
        else:
            return f"Anime #{self.media_item.id}"
    
    def get_progress_display(self) -> str:
        """Get a human-readable progress display."""
        if self.media_item.episodes:
            return f"{self.last_watched_episode}/{self.media_item.episodes}"
        else:
            return f"Ep {self.last_watched_episode}"
    
    def get_status_emoji(self) -> str:
        """Get emoji representation of status."""
        status_emojis = {
            "watching": "📺",
            "completed": "✅",
            "dropped": "🚮",
            "paused": "⏸️",
            "planning": "📑"
        }
        return status_emojis.get(self.status, "❓")


class WatchHistoryData(BaseModel):
    """Complete watch history data container."""
    
    entries: Dict[int, WatchHistoryEntry] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.now)
    format_version: str = "1.0"
    
    # With Pydantic, serialization is automatic!
    # No need for manual to_dict() and from_dict() methods
    # Use: data.model_dump() and WatchHistoryData.model_validate(data)
    
    def add_or_update_entry(self, media_item: MediaItem, episode: int = 0, progress: float = 0.0, status: str = "watching") -> WatchHistoryEntry:
        """Add or update a watch history entry."""
        media_id = media_item.id
        
        if media_id in self.entries:
            # Update existing entry
            entry = self.entries[media_id]
            entry.update_progress(episode, progress, status)
            entry.times_watched += 1
        else:
            # Create new entry
            entry = WatchHistoryEntry(
                media_item=media_item,
                last_watched_episode=episode,
                watch_progress=progress,
                status=status,
            )
            self.entries[media_id] = entry
        
        self.last_updated = datetime.now()
        return entry
    
    def get_entry(self, media_id: int) -> Optional[WatchHistoryEntry]:
        """Get a specific watch history entry."""
        return self.entries.get(media_id)
    
    def remove_entry(self, media_id: int) -> bool:
        """Remove an entry from watch history."""
        if media_id in self.entries:
            del self.entries[media_id]
            self.last_updated = datetime.now()
            return True
        return False
    
    def get_entries_by_status(self, status: str) -> List[WatchHistoryEntry]:
        """Get all entries with a specific status."""
        return [entry for entry in self.entries.values() if entry.status == status]
    
    def get_recently_watched(self, limit: int = 10) -> List[WatchHistoryEntry]:
        """Get recently watched entries."""
        sorted_entries = sorted(
            self.entries.values(),
            key=lambda x: x.last_watched,
            reverse=True
        )
        return sorted_entries[:limit]
    
    def get_watching_entries(self) -> List[WatchHistoryEntry]:
        """Get entries that are currently being watched."""
        return self.get_entries_by_status("watching")
    
    def get_completed_entries(self) -> List[WatchHistoryEntry]:
        """Get completed entries."""
        return self.get_entries_by_status("completed")
    
    def search_entries(self, query: str) -> List[WatchHistoryEntry]:
        """Search entries by title."""
        query_lower = query.lower()
        results = []
        
        for entry in self.entries.values():
            title = entry.get_display_title().lower()
            if query_lower in title:
                results.append(entry)
        
        return results
    
    def get_stats(self) -> dict:
        """Get watch history statistics."""
        total_entries = len(self.entries)
        watching = len(self.get_entries_by_status("watching"))
        completed = len(self.get_entries_by_status("completed"))
        dropped = len(self.get_entries_by_status("dropped"))
        paused = len(self.get_entries_by_status("paused"))
        
        total_episodes = sum(
            entry.last_watched_episode 
            for entry in self.entries.values()
        )
        
        return {
            "total_entries": total_entries,
            "watching": watching,
            "completed": completed,
            "dropped": dropped,
            "paused": paused,
            "total_episodes_watched": total_episodes,
            "last_updated": self.last_updated.strftime("%Y-%m-%d %H:%M:%S"),
        }
