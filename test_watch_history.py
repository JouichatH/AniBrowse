#!/usr/bin/env python3
"""
Test script for watch history management implementation.
Tests basic functionality without requiring full interactive session.
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastanime.cli.utils.watch_history_manager import WatchHistoryManager
from fastanime.cli.utils.watch_history_tracker import WatchHistoryTracker
from fastanime.libs.api.types import MediaItem, MediaTitle, MediaImage


def test_watch_history():
    """Test basic watch history functionality."""
    print("Testing Watch History Management System")
    print("=" * 50)
    
    # Create test media item
    test_anime = MediaItem(
        id=123456,
        id_mal=12345,
        title=MediaTitle(
            english="Test Anime",
            romaji="Test Anime Romaji",
            native="テストアニメ"
        ),
        episodes=24,
        cover_image=MediaImage(
            large="https://example.com/cover.jpg",
            medium="https://example.com/cover_medium.jpg"
        ),
        genres=["Action", "Adventure"],
        average_score=85.0
    )
    
    # Test watch history manager
    print("\n1. Testing WatchHistoryManager...")
    history_manager = WatchHistoryManager()
    
    # Add anime to history
    success = history_manager.add_or_update_entry(
        test_anime,
        episode=5,
        progress=0.8,
        status="watching",
        notes="Great anime so far!"
    )
    print(f"   Added anime to history: {success}")
    
    # Get entry back
    entry = history_manager.get_entry(123456)
    if entry:
        print(f"   Retrieved entry: {entry.get_display_title()}")
        print(f"   Progress: {entry.get_progress_display()}")
        print(f"   Status: {entry.status}")
        print(f"   Notes: {entry.notes}")
    else:
        print("   Failed to retrieve entry")
    
    # Test tracker
    print("\n2. Testing WatchHistoryTracker...")
    tracker = WatchHistoryTracker()
    
    # Track episode viewing
    success = tracker.track_episode_start(test_anime, 6)
    print(f"   Started tracking episode 6: {success}")
    
    # Complete episode
    success = tracker.track_episode_completion(123456, 6)
    print(f"   Completed episode 6: {success}")
    
    # Get progress
    progress = tracker.get_watch_progress(123456)
    if progress:
        print(f"   Current progress: Episode {progress['last_episode']}")
        print(f"   Next episode: {progress['next_episode']}")
        print(f"   Status: {progress['status']}")
    
    # Test stats
    print("\n3. Testing Statistics...")
    stats = history_manager.get_stats()
    print(f"   Total entries: {stats['total_entries']}")
    print(f"   Watching: {stats['watching']}")
    print(f"   Total episodes watched: {stats['total_episodes_watched']}")
    
    # Test search
    print("\n4. Testing Search...")
    search_results = history_manager.search_entries("Test")
    print(f"   Search results for 'Test': {len(search_results)} found")
    
    # Test status updates
    print("\n5. Testing Status Updates...")
    success = history_manager.change_status(123456, "completed")
    print(f"   Changed status to completed: {success}")
    
    # Verify status change
    entry = history_manager.get_entry(123456)
    if entry:
        print(f"   New status: {entry.status}")
    
    print("\n" + "=" * 50)
    print("Watch History Test Complete!")
    
    # Cleanup test data
    history_manager.remove_entry(123456)
    print("Test data cleaned up.")


if __name__ == "__main__":
    test_watch_history()
