"""
Watch history data models and types for the interactive CLI.
Provides comprehensive data structures for tracking and managing local watch history.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from ...libs.api.types import MediaItem

logger = logging.getLogger(__name__)


@dataclass
class WatchHistoryEntry:
    """
    Represents a single entry in the watch history.
    Contains media information and viewing progress.
    """
    
    media_item: MediaItem
    last_watched_episode: int = 0
    watch_progress: float = 0.0  # Progress within the episode (0.0-1.0)
    times_watched: int = 1
    first_watched: datetime = field(default_factory=datetime.now)
    last_watched: datetime = field(default_factory=datetime.now)
    status: str = "watching"  # watching, completed, dropped, paused
    notes: str = ""
    
    def to_dict(self) -> dict:
        """Convert entry to dictionary for JSON serialization."""
        return {
            "media_item": {
                "id": self.media_item.id,
                "id_mal": self.media_item.id_mal,
                "type": self.media_item.type,
                "title": {
                    "romaji": self.media_item.title.romaji,
                    "english": self.media_item.title.english,
                    "native": self.media_item.title.native,
                },
                "status": self.media_item.status,
                "format": self.media_item.format,
                "cover_image": {
                    "large": self.media_item.cover_image.large if self.media_item.cover_image else None,
                    "medium": self.media_item.cover_image.medium if self.media_item.cover_image else None,
                } if self.media_item.cover_image else None,
                "banner_image": self.media_item.banner_image,
                "description": self.media_item.description,
                "episodes": self.media_item.episodes,
                "duration": self.media_item.duration,
                "genres": self.media_item.genres,
                "synonyms": self.media_item.synonyms,
                "average_score": self.media_item.average_score,
                "popularity": self.media_item.popularity,
                "favourites": self.media_item.favourites,
            },
            "last_watched_episode": self.last_watched_episode,
            "watch_progress": self.watch_progress,
            "times_watched": self.times_watched,
            "first_watched": self.first_watched.isoformat(),
            "last_watched": self.last_watched.isoformat(),
            "status": self.status,
            "notes": self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "WatchHistoryEntry":
        """Create entry from dictionary."""
        from ...libs.api.types import MediaImage, MediaTitle
        
        media_data = data["media_item"]
        
        # Reconstruct MediaTitle
        title_data = media_data.get("title", {})
        title = MediaTitle(
            romaji=title_data.get("romaji"),
            english=title_data.get("english"),
            native=title_data.get("native"),
        )
        
        # Reconstruct MediaImage if present
        cover_data = media_data.get("cover_image")
        cover_image = None
        if cover_data:
            cover_image = MediaImage(
                large=cover_data.get("large", ""),
                medium=cover_data.get("medium"),
            )
        
        # Reconstruct MediaItem
        media_item = MediaItem(
            id=media_data["id"],
            id_mal=media_data.get("id_mal"),
            type=media_data.get("type", "ANIME"),
            title=title,
            status=media_data.get("status"),
            format=media_data.get("format"),
            cover_image=cover_image,
            banner_image=media_data.get("banner_image"),
            description=media_data.get("description"),
            episodes=media_data.get("episodes"),
            duration=media_data.get("duration"),
            genres=media_data.get("genres", []),
            synonyms=media_data.get("synonyms", []),
            average_score=media_data.get("average_score"),
            popularity=media_data.get("popularity"),
            favourites=media_data.get("favourites"),
        )
        
        return cls(
            media_item=media_item,
            last_watched_episode=data.get("last_watched_episode", 0),
            watch_progress=data.get("watch_progress", 0.0),
            times_watched=data.get("times_watched", 1),
            first_watched=datetime.fromisoformat(data.get("first_watched", datetime.now().isoformat())),
            last_watched=datetime.fromisoformat(data.get("last_watched", datetime.now().isoformat())),
            status=data.get("status", "watching"),
            notes=data.get("notes", ""),
        )
    
    def update_progress(self, episode: int, progress: float = 0.0, status: str = None):
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


@dataclass
class WatchHistoryData:
    """Complete watch history data container."""
    
    entries: Dict[int, WatchHistoryEntry] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)
    format_version: str = "1.0"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "entries": {str(k): v.to_dict() for k, v in self.entries.items()},
            "last_updated": self.last_updated.isoformat(),
            "format_version": self.format_version,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "WatchHistoryData":
        """Create from dictionary."""
        entries = {}
        entries_data = data.get("entries", {})
        
        for media_id_str, entry_data in entries_data.items():
            try:
                media_id = int(media_id_str)
                entry = WatchHistoryEntry.from_dict(entry_data)
                entries[media_id] = entry
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping invalid watch history entry {media_id_str}: {e}")
        
        return cls(
            entries=entries,
            last_updated=datetime.fromisoformat(data.get("last_updated", datetime.now().isoformat())),
            format_version=data.get("format_version", "1.0"),
        )
    
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
