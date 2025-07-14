"""
Test script to verify the feedback system works correctly.
Run this to see the feedback system in action.
"""

import sys
import time
from pathlib import Path

# Add the project root to the path so we can import fastanime modules
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fastanime.cli.utils.feedback import create_feedback_manager, execute_with_feedback


def test_feedback_system():
    """Test all feedback system components."""
    print("=== Testing FastAnime Enhanced Feedback System ===\n")

    # Test with icons enabled
    feedback = create_feedback_manager(icons_enabled=True)

    print("1. Testing success message:")
    feedback.success("Operation completed successfully", "All data has been processed")
    time.sleep(1)

    print("\n2. Testing error message:")
    feedback.error("Failed to connect to server", "Network timeout after 30 seconds")
    time.sleep(1)

    print("\n3. Testing warning message:")
    feedback.warning(
        "Anime not found on provider", "Try searching with a different title"
    )
    time.sleep(1)

    print("\n4. Testing info message:")
    feedback.info("Loading anime data", "This may take a few moments")
    time.sleep(1)

    print("\n5. Testing loading operation:")

    def mock_long_operation():
        time.sleep(2)
        return "Operation result"

    success, result = execute_with_feedback(
        mock_long_operation,
        feedback,
        "fetch anime data",
        loading_msg="Fetching anime from AniList",
        success_msg="Anime data loaded successfully",
    )

    print(f"Operation success: {success}, Result: {result}")

    print("\n6. Testing confirmation dialog:")
    if feedback.confirm("Do you want to continue with the test?", default=True):
        feedback.success("User confirmed to continue")
    else:
        feedback.info("User chose to stop")

    print("\n7. Testing detailed panel:")
    feedback.show_detailed_panel(
        "Anime Information",
        "Title: Attack on Titan\nGenres: Action, Drama\nStatus: Completed\nEpisodes: 25",
        "cyan",
    )

    print("\n=== Test completed! ===")


if __name__ == "__main__":
    test_feedback_system()
