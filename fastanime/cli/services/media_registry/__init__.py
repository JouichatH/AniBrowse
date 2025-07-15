"""
Unified Media Registry for FastAnime.

This module provides a unified system for tracking both watch history and downloads
for anime, eliminating data duplication between separate systems.
"""

from .manager import MediaRegistryManager, get_media_registry
from .models import (
    EpisodeStatus,
    MediaRecord,
    MediaRegistryIndex,
    UserMediaData,
)
from .tracker import MediaTracker, get_media_tracker

__all__ = [
    "MediaRegistryManager",
    "get_media_registry", 
    "EpisodeStatus",
    "MediaRecord",
    "MediaRegistryIndex",
    "UserMediaData",
    "MediaTracker",
    "get_media_tracker",
]
