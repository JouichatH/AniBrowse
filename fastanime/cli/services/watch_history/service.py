"""
Watch history manager for local storage operations.
Handles saving, loading, and managing local watch history data.
"""

import json
import logging
from pathlib import Path
from typing import List, Optional

from ....core.constants import USER_WATCH_HISTORY_PATH
from ....libs.api.types import MediaItem
from .types import WatchHistoryData, WatchHistoryEntry

logger = logging.getLogger(__name__)


class WatchHistoryService:
    """
    Manages local watch history storage and operations.
    Provides comprehensive watch history management with error handling.
    """

    def __init__(self, history_file_path: Path = USER_WATCH_HISTORY_PATH):
        self.history_file_path = history_file_path
        self._data: Optional[WatchHistoryData] = None
        self._ensure_history_file()

    def _ensure_history_file(self):
        """Ensure the watch history file and directory exist."""
        try:
            self.history_file_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.history_file_path.exists():
                # Create empty watch history file
                empty_data = WatchHistoryData()
                self._save_data(empty_data)
                logger.info(
                    f"Created new watch history file at {self.history_file_path}"
                )
        except Exception as e:
            logger.error(f"Failed to ensure watch history file: {e}")

    def _load_data(self) -> WatchHistoryData:
        """Load watch history data from file."""
        if self._data is not None:
            return self._data

        try:
            if not self.history_file_path.exists():
                self._data = WatchHistoryData()
                return self._data

            with self.history_file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            self._data = WatchHistoryData.from_dict(data)
            logger.debug(f"Loaded watch history with {len(self._data.entries)} entries")
            return self._data

        except json.JSONDecodeError as e:
            logger.error(f"Watch history file is corrupted: {e}")
            # Create backup of corrupted file
            backup_path = self.history_file_path.with_suffix(".backup")
            self.history_file_path.rename(backup_path)
            logger.info(f"Corrupted file moved to {backup_path}")

            # Create new empty data
            self._data = WatchHistoryData()
            self._save_data(self._data)
            return self._data

        except Exception as e:
            logger.error(f"Failed to load watch history: {e}")
            self._data = WatchHistoryData()
            return self._data

    def _save_data(self, data: WatchHistoryData) -> bool:
        """Save watch history data to file."""
        try:
            # Create backup of existing file
            if self.history_file_path.exists():
                backup_path = self.history_file_path.with_suffix(".bak")
                self.history_file_path.rename(backup_path)

            with self.history_file_path.open("w", encoding="utf-8") as f:
                json.dump(data.to_dict(), f, indent=2, ensure_ascii=False)

            # Remove backup on successful save
            backup_path = self.history_file_path.with_suffix(".bak")
            if backup_path.exists():
                backup_path.unlink()

            logger.debug(f"Saved watch history with {len(data.entries)} entries")
            return True

        except Exception as e:
            logger.error(f"Failed to save watch history: {e}")
            # Restore backup if save failed
            backup_path = self.history_file_path.with_suffix(".bak")
            if backup_path.exists():
                backup_path.rename(self.history_file_path)
            return False

    def add_or_update_entry(
        self,
        media_item: MediaItem,
        episode: int = 0,
        progress: float = 0.0,
        status: str = "watching",
        notes: str = "",
    ) -> bool:
        """Add or update a watch history entry."""
        try:
            data = self._load_data()
            entry = data.add_or_update_entry(media_item, episode, progress, status)
            if notes:
                entry.notes = notes

            success = self._save_data(data)
            if success:
                self._data = data  # Update cached data
                logger.info(f"Updated watch history for {entry.get_display_title()}")
            return success

        except Exception as e:
            logger.error(f"Failed to add/update watch history entry: {e}")
            return False

    def get_entry(self, media_id: int) -> Optional[WatchHistoryEntry]:
        """Get a specific watch history entry."""
        try:
            data = self._load_data()
            return data.get_entry(media_id)
        except Exception as e:
            logger.error(f"Failed to get watch history entry: {e}")
            return None

    def remove_entry(self, media_id: int) -> bool:
        """Remove an entry from watch history."""
        try:
            data = self._load_data()
            removed = data.remove_entry(media_id)

            if removed:
                success = self._save_data(data)
                if success:
                    self._data = data
                    logger.info(f"Removed watch history entry for media ID {media_id}")
                return success
            return False

        except Exception as e:
            logger.error(f"Failed to remove watch history entry: {e}")
            return False

    def get_all_entries(self) -> List[WatchHistoryEntry]:
        """Get all watch history entries."""
        try:
            data = self._load_data()
            return list(data.entries.values())
        except Exception as e:
            logger.error(f"Failed to get all entries: {e}")
            return []

    def get_entries_by_status(self, status: str) -> List[WatchHistoryEntry]:
        """Get entries by status (watching, completed, etc.)."""
        try:
            data = self._load_data()
            return data.get_entries_by_status(status)
        except Exception as e:
            logger.error(f"Failed to get entries by status: {e}")
            return []

    def get_recently_watched(self, limit: int = 10) -> List[WatchHistoryEntry]:
        """Get recently watched entries."""
        try:
            data = self._load_data()
            return data.get_recently_watched(limit)
        except Exception as e:
            logger.error(f"Failed to get recently watched: {e}")
            return []

    def search_entries(self, query: str) -> List[WatchHistoryEntry]:
        """Search entries by title."""
        try:
            data = self._load_data()
            return data.search_entries(query)
        except Exception as e:
            logger.error(f"Failed to search entries: {e}")
            return []

    def get_watching_entries(self) -> List[WatchHistoryEntry]:
        """Get entries that are currently being watched."""
        return self.get_entries_by_status("watching")

    def get_completed_entries(self) -> List[WatchHistoryEntry]:
        """Get completed entries."""
        return self.get_entries_by_status("completed")

    def mark_episode_watched(
        self, media_id: int, episode: int, progress: float = 1.0
    ) -> bool:
        """Mark a specific episode as watched."""
        entry = self.get_entry(media_id)
        if entry:
            return self.add_or_update_entry(
                entry.media_item, episode, progress, entry.status
            )
        return False

    def mark_completed(self, media_id: int) -> bool:
        """Mark an anime as completed."""
        entry = self.get_entry(media_id)
        if entry:
            entry.mark_completed()
            data = self._load_data()
            return self._save_data(data)
        return False

    def change_status(self, media_id: int, new_status: str) -> bool:
        """Change the status of an entry."""
        entry = self.get_entry(media_id)
        if entry:
            return self.add_or_update_entry(
                entry.media_item,
                entry.last_watched_episode,
                entry.watch_progress,
                new_status,
            )
        return False

    def update_notes(self, media_id: int, notes: str) -> bool:
        """Update notes for an entry."""
        entry = self.get_entry(media_id)
        if entry:
            return self.add_or_update_entry(
                entry.media_item,
                entry.last_watched_episode,
                entry.watch_progress,
                entry.status,
                notes,
            )
        return False

    def get_stats(self) -> dict:
        """Get watch history statistics."""
        try:
            data = self._load_data()
            return data.get_stats()
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                "total_entries": 0,
                "watching": 0,
                "completed": 0,
                "dropped": 0,
                "paused": 0,
                "total_episodes_watched": 0,
                "last_updated": "Unknown",
            }

    def export_history(self, export_path: Path) -> bool:
        """Export watch history to a file."""
        try:
            data = self._load_data()
            with export_path.open("w", encoding="utf-8") as f:
                json.dump(data.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Exported watch history to {export_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export watch history: {e}")
            return False

    def import_history(self, import_path: Path, merge: bool = True) -> bool:
        """Import watch history from a file."""
        try:
            if not import_path.exists():
                logger.error(f"Import file does not exist: {import_path}")
                return False

            with import_path.open("r", encoding="utf-8") as f:
                import_data = json.load(f)

            imported_history = WatchHistoryData.from_dict(import_data)

            if merge:
                # Merge with existing data
                current_data = self._load_data()
                for media_id, entry in imported_history.entries.items():
                    current_data.entries[media_id] = entry
                success = self._save_data(current_data)
            else:
                # Replace existing data
                success = self._save_data(imported_history)

            if success:
                self._data = None  # Force reload on next access
                logger.info(f"Imported watch history from {import_path}")

            return success

        except Exception as e:
            logger.error(f"Failed to import watch history: {e}")
            return False

    def clear_history(self) -> bool:
        """Clear all watch history."""
        try:
            empty_data = WatchHistoryData()
            success = self._save_data(empty_data)
            if success:
                self._data = empty_data
                logger.info("Cleared all watch history")
            return success
        except Exception as e:
            logger.error(f"Failed to clear watch history: {e}")
            return False

    def backup_history(self, backup_path: Path = None) -> bool:
        """Create a backup of watch history."""
        try:
            if backup_path is None:
                from datetime import datetime

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = (
                    self.history_file_path.parent
                    / f"watch_history_backup_{timestamp}.json"
                )

            return self.export_history(backup_path)
        except Exception as e:
            logger.error(f"Failed to backup watch history: {e}")
            return False

    def get_entry_by_media_id(self, media_id: int) -> Optional[WatchHistoryEntry]:
        """Get watch history entry by media ID (alias for get_entry)."""
        return self.get_entry(media_id)

    def save_entry(self, entry: WatchHistoryEntry) -> bool:
        """Save a watch history entry (alias for add_or_update_entry)."""
        return self.add_or_update_entry(
            entry.media_item,
            entry.status,
            entry.last_watched_episode,
            entry.watch_progress,
        )

    def get_currently_watching(self) -> List[WatchHistoryEntry]:
        """Get entries that are currently being watched."""
        return self.get_watching_entries()
