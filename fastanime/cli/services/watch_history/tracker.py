"""
Watch history tracking utilities for integration with episode viewing and player controls.
Provides automatic watch history updates during episode viewing.
"""

import logging
from typing import Optional

from ....libs.api.types import MediaItem
from .manager import WatchHistoryManager

logger = logging.getLogger(__name__)


class WatchHistoryTracker:
    """
    Tracks watch history automatically during episode viewing.
    Integrates with the episode selection and player control systems.
    """
    
    def __init__(self):
        self.history_manager = WatchHistoryManager()
    
    def track_episode_start(self, media_item: MediaItem, episode: int) -> bool:
        """
        Track when an episode starts being watched.
        
        Args:
            media_item: The anime being watched
            episode: Episode number being started
            
        Returns:
            True if tracking was successful
        """
        try:
            # Update or create watch history entry
            success = self.history_manager.add_or_update_entry(
                media_item=media_item,
                episode=episode,
                progress=0.0,
                status="watching"
            )
            
            if success:
                logger.info(f"Started tracking episode {episode} of {media_item.title.english or media_item.title.romaji}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to track episode start: {e}")
            return False
    
    def track_episode_progress(self, media_id: int, episode: int, progress: float) -> bool:
        """
        Track progress within an episode.
        
        Args:
            media_id: ID of the anime
            episode: Episode number
            progress: Progress within the episode (0.0-1.0)
            
        Returns:
            True if tracking was successful
        """
        try:
            success = self.history_manager.mark_episode_watched(media_id, episode, progress)
            
            if success and progress >= 0.8:  # Consider episode "watched" at 80%
                logger.info(f"Episode {episode} marked as watched (progress: {progress:.1%})")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to track episode progress: {e}")
            return False
    
    def track_episode_completion(self, media_id: int, episode: int) -> bool:
        """
        Track when an episode is completed.
        
        Args:
            media_id: ID of the anime
            episode: Episode number completed
            
        Returns:
            True if tracking was successful
        """
        try:
            # Mark episode as fully watched
            success = self.history_manager.mark_episode_watched(media_id, episode, 1.0)
            
            if success:
                # Check if this was the final episode and mark as completed
                entry = self.history_manager.get_entry(media_id)
                if entry and entry.media_item.episodes and episode >= entry.media_item.episodes:
                    self.history_manager.mark_completed(media_id)
                    logger.info(f"Anime completed: {entry.get_display_title()}")
                else:
                    logger.info(f"Episode {episode} completed")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to track episode completion: {e}")
            return False
    
    def get_watch_progress(self, media_id: int) -> Optional[dict]:
        """
        Get current watch progress for an anime.
        
        Args:
            media_id: ID of the anime
            
        Returns:
            Dictionary with progress info or None if not found
        """
        try:
            entry = self.history_manager.get_entry(media_id)
            if entry:
                return {
                    "last_episode": entry.last_watched_episode,
                    "progress": entry.watch_progress,
                    "status": entry.status,
                    "next_episode": entry.last_watched_episode + 1,
                    "title": entry.get_display_title(),
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to get watch progress: {e}")
            return None
    
    def should_continue_from_history(self, media_id: int, available_episodes: list) -> Optional[str]:
        """
        Determine if we should continue from watch history and which episode.
        
        Args:
            media_id: ID of the anime
            available_episodes: List of available episode numbers
            
        Returns:
            Episode number to continue from, or None if no history
        """
        try:
            progress = self.get_watch_progress(media_id)
            if not progress:
                return None
            
            last_episode = progress["last_episode"]
            next_episode = last_episode + 1
            
            # Check if next episode is available
            if str(next_episode) in available_episodes:
                logger.info(f"Continuing from episode {next_episode} based on watch history")
                return str(next_episode)
            # Fall back to last watched episode if next isn't available
            elif str(last_episode) in available_episodes and last_episode > 0:
                logger.info(f"Next episode not available, falling back to episode {last_episode}")
                return str(last_episode)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to determine continue episode: {e}")
            return None
    
    def update_anime_status(self, media_id: int, status: str) -> bool:
        """
        Update the status of an anime in watch history.
        
        Args:
            media_id: ID of the anime
            status: New status (watching, completed, dropped, paused)
            
        Returns:
            True if update was successful
        """
        try:
            success = self.history_manager.change_status(media_id, status)
            if success:
                logger.info(f"Updated anime status to {status}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to update anime status: {e}")
            return False
    
    def add_anime_to_history(self, media_item: MediaItem, status: str = "planning") -> bool:
        """
        Add an anime to watch history without watching any episodes.
        
        Args:
            media_item: The anime to add
            status: Initial status
            
        Returns:
            True if successful
        """
        try:
            success = self.history_manager.add_or_update_entry(
                media_item=media_item,
                episode=0,
                progress=0.0,
                status=status
            )
            
            if success:
                logger.info(f"Added {media_item.title.english or media_item.title.romaji} to watch history")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to add anime to history: {e}")
            return False


# Global tracker instance for use throughout the application
watch_tracker = WatchHistoryTracker()


def track_episode_viewing(media_item: MediaItem, episode: int, start_tracking: bool = True) -> bool:
    """
    Convenience function to track episode viewing.
    
    Args:
        media_item: The anime being watched
        episode: Episode number
        start_tracking: Whether to start tracking (True) or just update progress
        
    Returns:
        True if tracking was successful
    """
    if start_tracking:
        return watch_tracker.track_episode_start(media_item, episode)
    else:
        return watch_tracker.track_episode_completion(media_item.id, episode)


def get_continue_episode(media_item: MediaItem, available_episodes: list, prefer_history: bool = True) -> Optional[str]:
    """
    Get the episode to continue from based on watch history.
    
    Args:
        media_item: The anime
        available_episodes: List of available episodes
        prefer_history: Whether to prefer local history over remote
        
    Returns:
        Episode number to continue from
    """
    if prefer_history:
        return watch_tracker.should_continue_from_history(media_item.id, available_episodes)
    return None


def update_episode_progress(media_id: int, episode: int, completion_percentage: float) -> bool:
    """
    Update progress for an episode based on completion percentage.
    
    Args:
        media_id: ID of the anime
        episode: Episode number
        completion_percentage: Completion percentage (0-100)
        
    Returns:
        True if update was successful
    """
    progress = completion_percentage / 100.0
    
    if completion_percentage >= 80:  # Consider episode completed at 80%
        return watch_tracker.track_episode_completion(media_id, episode)
    else:
        return watch_tracker.track_episode_progress(media_id, episode, progress)
