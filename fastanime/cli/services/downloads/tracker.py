"""
Download progress tracking and integration with the download system.

This module provides real-time tracking of download progress and integrates
with the existing download infrastructure to provide progress updates.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional

from ....core.config.model import DownloadsConfig
from .manager import DownloadManager, get_download_manager
from .models import DownloadQueueItem

logger = logging.getLogger(__name__)

# Type alias for progress callback
ProgressCallback = Callable[[int, int, float, float], None]  # media_id, episode, progress, speed


class DownloadTracker:
    """
    Tracks download progress and integrates with the download manager.
    
    Provides real-time progress updates and handles integration between
    the actual download process and the tracking system.
    """
    
    def __init__(self, config: DownloadsConfig):
        self.config = config
        self.download_manager = get_download_manager(config)
        
        # Track active downloads
        self._active_downloads: Dict[str, DownloadSession] = {}
        self._lock = threading.RLock()
        
        # Progress callbacks
        self._progress_callbacks: list[ProgressCallback] = []
    
    def add_progress_callback(self, callback: ProgressCallback) -> None:
        """Add a callback function to receive progress updates."""
        with self._lock:
            self._progress_callbacks.append(callback)
    
    def remove_progress_callback(self, callback: ProgressCallback) -> None:
        """Remove a progress callback."""
        with self._lock:
            if callback in self._progress_callbacks:
                self._progress_callbacks.remove(callback)
    
    def start_download(self, queue_item: DownloadQueueItem) -> str:
        """Start tracking a download and return session ID."""
        with self._lock:
            session_id = f"{queue_item.media_id}_{queue_item.episode_number}_{int(time.time())}"
            
            session = DownloadSession(
                session_id=session_id,
                queue_item=queue_item,
                tracker=self
            )
            
            self._active_downloads[session_id] = session
            
            # Mark download as started in manager
            self.download_manager.mark_download_started(
                queue_item.media_id, 
                queue_item.episode_number
            )
            
            logger.info(f"Started download tracking for session {session_id}")
            return session_id
    
    def update_progress(self, session_id: str, progress: float, 
                       speed: Optional[float] = None) -> None:
        """Update download progress for a session."""
        with self._lock:
            if session_id not in self._active_downloads:
                logger.warning(f"Unknown download session: {session_id}")
                return
            
            session = self._active_downloads[session_id]
            session.update_progress(progress, speed)
            
            # Notify callbacks
            for callback in self._progress_callbacks:
                try:
                    callback(
                        session.queue_item.media_id,
                        session.queue_item.episode_number,
                        progress,
                        speed or 0.0
                    )
                except Exception as e:
                    logger.error(f"Error in progress callback: {e}")
    
    def complete_download(self, session_id: str, file_path: Path, 
                         file_size: int, checksum: Optional[str] = None) -> bool:
        """Mark a download as completed."""
        with self._lock:
            if session_id not in self._active_downloads:
                logger.warning(f"Unknown download session: {session_id}")
                return False
            
            session = self._active_downloads[session_id]
            session.mark_completed(file_path, file_size, checksum)
            
            # Update download manager
            success = self.download_manager.mark_download_completed(
                session.queue_item.media_id,
                session.queue_item.episode_number,
                file_path,
                file_size,
                checksum
            )
            
            # Remove from active downloads
            del self._active_downloads[session_id]
            
            logger.info(f"Completed download session {session_id}")
            return success
    
    def fail_download(self, session_id: str, error_message: str) -> bool:
        """Mark a download as failed."""
        with self._lock:
            if session_id not in self._active_downloads:
                logger.warning(f"Unknown download session: {session_id}")
                return False
            
            session = self._active_downloads[session_id]
            session.mark_failed(error_message)
            
            # Update download manager
            success = self.download_manager.mark_download_failed(
                session.queue_item.media_id,
                session.queue_item.episode_number,
                error_message
            )
            
            # Remove from active downloads
            del self._active_downloads[session_id]
            
            logger.warning(f"Failed download session {session_id}: {error_message}")
            return success
    
    def get_active_downloads(self) -> Dict[str, 'DownloadSession']:
        """Get all currently active download sessions."""
        with self._lock:
            return self._active_downloads.copy()
    
    def cancel_download(self, session_id: str) -> bool:
        """Cancel an active download."""
        with self._lock:
            if session_id not in self._active_downloads:
                return False
            
            session = self._active_downloads[session_id]
            session.cancel()
            
            # Mark as failed with cancellation message
            self.download_manager.mark_download_failed(
                session.queue_item.media_id,
                session.queue_item.episode_number,
                "Download cancelled by user"
            )
            
            del self._active_downloads[session_id]
            logger.info(f"Cancelled download session {session_id}")
            return True
    
    def cleanup_stale_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up stale download sessions that may have been orphaned."""
        with self._lock:
            current_time = datetime.now()
            stale_sessions = []
            
            for session_id, session in self._active_downloads.items():
                age_hours = (current_time - session.start_time).total_seconds() / 3600
                if age_hours > max_age_hours:
                    stale_sessions.append(session_id)
            
            for session_id in stale_sessions:
                self.fail_download(session_id, "Session timed out")
            
            return len(stale_sessions)


class DownloadSession:
    """
    Represents an active download session with progress tracking.
    """
    
    def __init__(self, session_id: str, queue_item: DownloadQueueItem, tracker: DownloadTracker):
        self.session_id = session_id
        self.queue_item = queue_item
        self.tracker = tracker
        self.start_time = datetime.now()
        
        # Progress tracking
        self.progress = 0.0
        self.download_speed = 0.0
        self.bytes_downloaded = 0
        self.total_bytes = queue_item.estimated_size or 0
        
        # Status
        self.is_cancelled = False
        self.is_completed = False
        self.error_message: Optional[str] = None
        
        # Thread safety
        self._lock = threading.Lock()
    
    def update_progress(self, progress: float, speed: Optional[float] = None) -> None:
        """Update the progress of this download session."""
        with self._lock:
            if self.is_cancelled or self.is_completed:
                return
            
            self.progress = max(0.0, min(1.0, progress))
            
            if speed is not None:
                self.download_speed = speed
            
            if self.total_bytes > 0:
                self.bytes_downloaded = int(self.total_bytes * self.progress)
            
            logger.debug(f"Session {self.session_id} progress: {self.progress:.2%}")
    
    def mark_completed(self, file_path: Path, file_size: int, checksum: Optional[str] = None) -> None:
        """Mark this session as completed."""
        with self._lock:
            if self.is_cancelled:
                return
            
            self.is_completed = True
            self.progress = 1.0
            self.bytes_downloaded = file_size
            self.total_bytes = file_size
    
    def mark_failed(self, error_message: str) -> None:
        """Mark this session as failed."""
        with self._lock:
            if self.is_cancelled or self.is_completed:
                return
            
            self.error_message = error_message
    
    def cancel(self) -> None:
        """Cancel this download session."""
        with self._lock:
            if self.is_completed:
                return
            
            self.is_cancelled = True
    
    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        return (datetime.now() - self.start_time).total_seconds()
    
    @property
    def estimated_time_remaining(self) -> Optional[float]:
        """Get estimated time remaining in seconds."""
        if self.progress <= 0 or self.download_speed <= 0:
            return None
        
        remaining_bytes = self.total_bytes - self.bytes_downloaded
        if remaining_bytes <= 0:
            return 0.0
        
        return remaining_bytes / self.download_speed
    
    @property
    def status_text(self) -> str:
        """Get human-readable status."""
        if self.is_cancelled:
            return "Cancelled"
        elif self.is_completed:
            return "Completed"
        elif self.error_message:
            return f"Failed: {self.error_message}"
        else:
            return f"Downloading ({self.progress:.1%})"


# Global tracker instance
_download_tracker: Optional[DownloadTracker] = None


def get_download_tracker(config: DownloadsConfig) -> DownloadTracker:
    """Get or create the global download tracker instance."""
    global _download_tracker
    
    if _download_tracker is None:
        _download_tracker = DownloadTracker(config)
    
    return _download_tracker
