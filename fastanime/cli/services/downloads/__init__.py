"""
Download tracking services for FastAnime.

This module provides comprehensive download tracking and management capabilities
including progress monitoring, queue management, and integration with watch history.
"""

from .manager import DownloadManager, get_download_manager
from .models import (
    DownloadIndex,
    DownloadQueueItem,
    EpisodeDownload,
    MediaDownloadRecord,
    MediaIndexEntry,
)
from .tracker import DownloadTracker, get_download_tracker

__all__ = [
    "DownloadManager",
    "get_download_manager",
    "DownloadTracker",
    "get_download_tracker",
    "EpisodeDownload",
    "MediaDownloadRecord",
    "DownloadIndex",
    "MediaIndexEntry",
    "DownloadQueueItem",
]
