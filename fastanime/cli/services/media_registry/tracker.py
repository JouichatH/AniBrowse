"""
Unified Media Tracker for player integration and real-time updates.

Provides automatic tracking of watch progress and download completion
through a single interface.
"""

from __future__ import annotations

import logging
from typing import Optional

from ....libs.api.types import MediaItem
from ....libs.players.types import PlayerResult
from .manager import MediaRegistryManager, get_media_registry

logger = logging.getLogger(__name__)


class MediaTracker:
    """
    Unified tracker for media interactions.
    
    Handles automatic updates from player results and download completion,
    providing seamless integration between watching and downloading.
    """
    
    def __init__(self, registry_manager: MediaRegistryManager = None):
        self.registry = registry_manager or get_media_registry()
    
    def track_episode_start(self, media_item: MediaItem, episode: int) -> bool:
        """
        Track when episode playback starts.
        
        Args:
            media_item: The anime being watched
            episode: Episode number being started
            
        Returns:
            True if tracking was successful
        """
        try:
            record = self.registry.get_or_create_record(media_item)
            episode_status = record.get_episode_status(episode)
            
            # Only update to "watching" if not already completed
            if episode_status.watch_status not in ["completed"]:
                episode_status.watch_status = "watching"
                
            # Update overall user status if still planning
            if record.user_data.status == "planning":
                record.user_data.status = "watching"
                
            return self.registry.save_media_record(record)
            
        except Exception as e:
            logger.error(f"Failed to track episode start: {e}")
            return False
    
    def track_from_player_result(self, media_item: MediaItem, episode: int, 
                                player_result: PlayerResult) -> bool:
        """
        Update watch status based on actual player feedback.
        
        Args:
            media_item: The anime that was watched
            episode: Episode number that was watched
            player_result: Result from the player session
            
        Returns:
            True if tracking was successful
        """
        try:
            if not player_result.stop_time or not player_result.total_time:
                logger.warning("PlayerResult missing timing data - cannot track accurately")
                return False
            
            return self.registry.update_from_player_result(
                media_item, episode, player_result.stop_time, player_result.total_time
            )
            
        except Exception as e:
            logger.error(f"Failed to track from player result: {e}")
            return False
    
    def track_download_completion(self, media_item: MediaItem, episode: int,
                                file_path, file_size: int, quality: str, 
                                checksum: Optional[str] = None) -> bool:
        """
        Update status when download completes.
        
        Args:
            media_item: The anime that was downloaded
            episode: Episode number that was downloaded
            file_path: Path to downloaded file
            file_size: File size in bytes
            quality: Download quality
            checksum: Optional file checksum
            
        Returns:
            True if tracking was successful
        """
        try:
            from pathlib import Path
            file_path = Path(file_path) if not isinstance(file_path, Path) else file_path
            
            return self.registry.update_download_completion(
                media_item, episode, file_path, file_size, quality, checksum
            )
            
        except Exception as e:
            logger.error(f"Failed to track download completion: {e}")
            return False
    
    def get_continue_episode(self, media_item: MediaItem, 
                           available_episodes: list) -> Optional[str]:
        """
        Get episode to continue watching based on history.
        
        Args:
            media_item: The anime
            available_episodes: List of available episode numbers
            
        Returns:
            Episode number to continue from or None
        """
        try:
            return self.registry.get_continue_episode(
                media_item.id, [str(ep) for ep in available_episodes]
            )
            
        except Exception as e:
            logger.error(f"Failed to get continue episode: {e}")
            return None
    
    def get_watch_progress(self, media_id: int) -> Optional[dict]:
        """
        Get current watch progress for an anime.
        
        Args:
            media_id: ID of the anime
            
        Returns:
            Dictionary with progress info or None if not found
        """
        try:
            record = self.registry.get_media_record(media_id)
            if not record:
                return None
            
            return {
                "last_episode": record.last_watched_episode,
                "next_episode": record.next_episode_to_watch,
                "status": record.user_data.status,
                "title": record.display_title,
                "watch_percentage": record.watch_completion_percentage,
                "download_percentage": record.download_completion_percentage,
                "episodes_watched": record.total_episodes_watched,
                "episodes_downloaded": record.total_episodes_downloaded,
            }
            
        except Exception as e:
            logger.error(f"Failed to get watch progress: {e}")
            return None
    
    def update_anime_status(self, media_id: int, status: str) -> bool:
        """
        Update overall anime status.
        
        Args:
            media_id: ID of the anime
            status: New status (planning, watching, completed, dropped, paused)
            
        Returns:
            True if update was successful
        """
        try:
            record = self.registry.get_media_record(media_id)
            if not record:
                return False
            
            if status in ["planning", "watching", "completed", "dropped", "paused"]:
                record.user_data.status = status
                record.user_data.update_timestamp()
                return self.registry.save_media_record(record)
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to update anime status: {e}")
            return False
    
    def add_anime_to_registry(self, media_item: MediaItem, status: str = "planning") -> bool:
        """
        Add anime to registry with initial status.
        
        Args:
            media_item: The anime to add
            status: Initial status
            
        Returns:
            True if added successfully
        """
        try:
            record = self.registry.get_or_create_record(media_item)
            if status in ["planning", "watching", "completed", "dropped", "paused"]:
                record.user_data.status = status
                record.user_data.update_timestamp()
                return self.registry.save_media_record(record)
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to add anime to registry: {e}")
            return False
    
    def should_auto_download_next(self, media_id: int) -> Optional[int]:
        """
        Check if next episode should be auto-downloaded based on watch progress.
        
        Args:
            media_id: ID of the anime
            
        Returns:
            Episode number to download or None
        """
        try:
            record = self.registry.get_media_record(media_id)
            if not record or not record.user_data.auto_download_new:
                return None
            
            # Only if currently watching
            if record.user_data.status != "watching":
                return None
            
            next_episode = record.next_episode_to_watch
            if not next_episode:
                return None
            
            # Check if already downloaded
            episode_status = record.episodes.get(next_episode)
            if episode_status and episode_status.is_available_locally:
                return None
            
            return next_episode
            
        except Exception as e:
            logger.error(f"Failed to check auto download: {e}")
            return None


# Global tracker instance
_media_tracker: Optional[MediaTracker] = None


def get_media_tracker() -> MediaTracker:
    """Get or create the global media tracker instance."""
    global _media_tracker
    if _media_tracker is None:
        _media_tracker = MediaTracker()
    return _media_tracker


# Convenience functions for backward compatibility
def track_episode_viewing(media_item: MediaItem, episode: int, start_tracking: bool = True) -> bool:
    """Track episode viewing (backward compatibility)."""
    tracker = get_media_tracker()
    return tracker.track_episode_start(media_item, episode)


def get_continue_episode(media_item: MediaItem, available_episodes: list, 
                       prefer_history: bool = True) -> Optional[str]:
    """Get continue episode (backward compatibility)."""
    if not prefer_history:
        return None
    
    tracker = get_media_tracker()
    return tracker.get_continue_episode(media_item, available_episodes)


def update_episode_progress(media_id: int, episode: int, completion_percentage: float) -> bool:
    """Update episode progress (backward compatibility)."""
    # This would need more context to implement properly with PlayerResult
    # For now, just mark as watched if 80%+
    if completion_percentage >= 80:
        tracker = get_media_tracker()
        registry = get_media_registry()
        return registry.mark_episode_watched(media_id, episode, completion_percentage / 100)
    return True
