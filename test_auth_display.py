"""
Test script to verify the authentication system works correctly.
This tests the auth utilities and their integration with the feedback system.
"""

import sys
from pathlib import Path

# Add the project root to the path so we can import fastanime modules
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fastanime.cli.utils.auth_utils import (
    get_auth_status_indicator,
    format_user_info_header,
    check_authentication_required,
    format_auth_menu_header,
    prompt_for_authentication,
)
from fastanime.cli.utils.feedback import create_feedback_manager
from fastanime.libs.api.types import UserProfile


class MockApiClient:
    """Mock API client for testing authentication utilities."""

    def __init__(self, authenticated=False):
        if authenticated:
            self.user_profile = UserProfile(
                id=12345,
                name="TestUser",
                avatar_url="https://example.com/avatar.jpg",
                banner_url="https://example.com/banner.jpg",
            )
        else:
            self.user_profile = None


def test_auth_status_display():
    """Test authentication status display functionality."""
    print("=== Testing Authentication Status Display ===\n")

    feedback = create_feedback_manager(icons_enabled=True)

    print("1. Testing authentication status when NOT logged in:")
    mock_api_not_auth = MockApiClient(authenticated=False)
    status_text, user_profile = get_auth_status_indicator(mock_api_not_auth, True)
    print(f"   Status: {status_text}")
    print(f"   User Profile: {user_profile}")

    print("\n2. Testing authentication status when logged in:")
    mock_api_auth = MockApiClient(authenticated=True)
    status_text, user_profile = get_auth_status_indicator(mock_api_auth, True)
    print(f"   Status: {status_text}")
    print(f"   User Profile: {user_profile}")

    print("\n3. Testing user info header formatting:")
    header = format_user_info_header(user_profile, True)
    print(f"   Header: {header}")

    print("\n4. Testing menu header formatting:")
    auth_header = format_auth_menu_header(mock_api_auth, "Test Menu", True)
    print(f"   Auth Header:\n{auth_header}")

    print("\n5. Testing authentication check (not authenticated):")
    is_auth = check_authentication_required(
        mock_api_not_auth, feedback, "test operation"
    )
    print(f"   Authentication passed: {is_auth}")

    print("\n6. Testing authentication check (authenticated):")
    is_auth = check_authentication_required(mock_api_auth, feedback, "test operation")
    print(f"   Authentication passed: {is_auth}")

    print("\n7. Testing authentication prompt:")
    # Note: This will show interactive prompts if run in a terminal
    # prompt_for_authentication(feedback, "access your anime list")
    print("   Skipped interactive prompt test - uncomment to test manually")

    print("\n=== Authentication Tests Completed! ===")


if __name__ == "__main__":
    test_auth_status_display()
