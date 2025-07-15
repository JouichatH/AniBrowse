"""
Synchronization service between watch history and download tracking.

This module provides functionality to keep watch history and download status
in sync, enabling features like offline availability markers and smart
download suggestions based on viewing patterns.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from ....libs.api.types import MediaItem
from ..downloads.manager import DownloadManager
from ..watch_history.manager import WatchHistoryManager
from ..watch_history.types import WatchHistoryEntry

logger = logging.getLogger(__name__)


class HistoryDownloadSync:
    """
    Service to synchronize watch history and download tracking.
    
    Provides bidirectional synchronization between viewing history and
    download status, enabling features like offline availability and
    smart download recommendations.
    """
    
    def __init__(self, watch_manager: WatchHistoryManager, download_manager: DownloadManager):
        self.watch_manager = watch_manager
        self.download_manager = download_manager
    
    def sync_download_status(self, media_id: int) -> bool:
        """
        Update watch history with download availability status.
        
        Args:
            media_id: The media ID to sync
            
        Returns:
            True if sync was successful
        """
        try:
            # Get download record
            download_record = self.download_manager.get_download_record(media_id)
            if not download_record:
                return False
            
            # Get watch history entry
            watch_entry = self.watch_manager.get_entry_by_media_id(media_id)
            if not watch_entry:
                return False
            
            # Check if any episodes are downloaded
            has_downloads = any(
                ep.is_completed for ep in download_record.episodes.values()
            )
            
            # Check if current/next episode is available offline
            current_episode = watch_entry.last_watched_episode
            next_episode = current_episode + 1
            
            offline_available = (
                current_episode in download_record.episodes and
                download_record.episodes[current_episode].is_completed
            ) or (
                next_episode in download_record.episodes and
                download_record.episodes[next_episode].is_completed
            )
            
            # Update watch history entry
            updated_entry = watch_entry.model_copy(update={
                "has_downloads": has_downloads,
                "offline_available": offline_available
            })
            
            return self.watch_manager.save_entry(updated_entry)
            
        except Exception as e:
            logger.error(f"Failed to sync download status for media {media_id}: {e}")
            return False
    
    def mark_episodes_offline_available(self, media_id: int, episodes: List[int]) -> bool:
        """
        Mark specific episodes as available offline in watch history.
        
        Args:
            media_id: The media ID
            episodes: List of episode numbers that are available offline
            
        Returns:
            True if successful
        """
        try:
            watch_entry = self.watch_manager.get_entry_by_media_id(media_id)
            if not watch_entry:
                return False
            
            # Check if current or next episode is in the available episodes
            current_episode = watch_entry.last_watched_episode
            next_episode = current_episode + 1
            
            offline_available = (
                current_episode in episodes or
                next_episode in episodes or
                len(episodes) > 0  # Any episodes available
            )
            
            updated_entry = watch_entry.model_copy(update={
                "has_downloads": len(episodes) > 0,
                "offline_available": offline_available
            })
            
            return self.watch_manager.save_entry(updated_entry)
            
        except Exception as e:
            logger.error(f"Failed to mark episodes offline available for media {media_id}: {e}")
            return False
    
    def suggest_downloads_for_watching(self, media_id: int, lookahead: int = 3) -> List[int]:
        """
        Suggest episodes to download based on watch history.
        
        Args:
            media_id: The media ID
            lookahead: Number of episodes ahead to suggest
            
        Returns:
            List of episode numbers to download
        """
        try:
            watch_entry = self.watch_manager.get_entry_by_media_id(media_id)
            if not watch_entry or watch_entry.status != "watching":
                return []
            
            download_record = self.download_manager.get_download_record(media_id)
            if not download_record:
                return []
            
            # Get currently downloaded episodes
            downloaded_episodes = set(
                ep_num for ep_num, ep in download_record.episodes.items()
                if ep.is_completed
            )
            
            # Suggest next episodes
            current_episode = watch_entry.last_watched_episode
            total_episodes = watch_entry.media_item.episodes or 999
            
            suggestions = []
            for i in range(1, lookahead + 1):
                next_episode = current_episode + i
                if (next_episode <= total_episodes and 
                    next_episode not in downloaded_episodes):
                    suggestions.append(next_episode)
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Failed to suggest downloads for media {media_id}: {e}")
            return []
    
    def suggest_downloads_for_completed(self, limit: int = 5) -> List[MediaItem]:
        """
        Suggest anime to download based on completed watch history.
        
        Args:
            limit: Maximum number of suggestions
            
        Returns:
            List of MediaItems to consider for download
        """
        try:
            # Get completed anime from watch history
            completed_entries = self.watch_manager.get_entries_by_status("completed")
            
            suggestions = []
            for entry in completed_entries[:limit]:
                # Check if not already fully downloaded
                download_record = self.download_manager.get_download_record(entry.media_item.id)
                
                if not download_record:
                    suggestions.append(entry.media_item)
                elif download_record.completion_percentage < 100:
                    suggestions.append(entry.media_item)
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Failed to suggest downloads for completed anime: {e}")
            return []
    
    def sync_all_entries(self) -> int:
        """
        Sync download status for all watch history entries.
        
        Returns:
            Number of entries successfully synced
        """
        try:
            watch_entries = self.watch_manager.get_all_entries()
            synced_count = 0
            
            for entry in watch_entries:
                if self.sync_download_status(entry.media_item.id):
                    synced_count += 1
            
            logger.info(f"Synced download status for {synced_count}/{len(watch_entries)} entries")
            return synced_count
            
        except Exception as e:
            logger.error(f"Failed to sync all entries: {e}")
            return 0
    
    def update_watch_progress_from_downloads(self, media_id: int) -> bool:
        """
        Update watch progress based on downloaded episodes.
        
        Useful when episodes are watched outside the app but files exist.
        
        Args:
            media_id: The media ID to update
            
        Returns:
            True if successful
        """
        try:
            download_record = self.download_manager.get_download_record(media_id)
            if not download_record:
                return False
            
            watch_entry = self.watch_manager.get_entry_by_media_id(media_id)
            if not watch_entry:
                # Create new watch entry if none exists
                watch_entry = WatchHistoryEntry(
                    media_item=download_record.media_item,
                    status="watching"
                )
            
            # Find highest downloaded episode
            downloaded_episodes = [
                ep_num for ep_num, ep in download_record.episodes.items()
                if ep.is_completed
            ]
            
            if downloaded_episodes:
                max_downloaded = max(downloaded_episodes)
                
                # Only update if we have more episodes downloaded than watched
                if max_downloaded > watch_entry.last_watched_episode:
                    updated_entry = watch_entry.model_copy(update={
                        "last_watched_episode": max_downloaded,
                        "watch_progress": 1.0,  # Assume completed if downloaded
                        "has_downloads": True,
                        "offline_available": True
                    })
                    
                    return self.watch_manager.save_entry(updated_entry)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update watch progress from downloads for media {media_id}: {e}")
            return False
    
    def get_offline_watchable_anime(self) -> List[WatchHistoryEntry]:
        """
        Get list of anime that can be watched offline.
        
        Returns:
            List of watch history entries with offline episodes available
        """
        try:
            watch_entries = self.watch_manager.get_all_entries()
            offline_entries = []
            
            for entry in watch_entries:
                if entry.offline_available:
                    offline_entries.append(entry)
                else:
                    # Double-check by looking at downloads
                    download_record = self.download_manager.get_download_record(entry.media_item.id)
                    if download_record:
                        next_episode = entry.last_watched_episode + 1
                        if (next_episode in download_record.episodes and 
                            download_record.episodes[next_episode].is_completed):
                            offline_entries.append(entry)
            
            return offline_entries
            
        except Exception as e:
            logger.error(f"Failed to get offline watchable anime: {e}")
            return []


def create_sync_service(watch_manager: WatchHistoryManager, 
                       download_manager: DownloadManager) -> HistoryDownloadSync:
    """Factory function to create a synchronization service."""
    return HistoryDownloadSync(watch_manager, download_manager)
