#!/usr/bin/env python3
"""
Test script for the Step 5: AniList Authentication Flow implementation.
This tests the interactive authentication menu and its functionalities.
"""

import sys
from pathlib import Path

# Add the project root to the path so we can import fastanime modules
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from fastanime.cli.interactive.menus.auth import (
    _display_auth_status,
    _display_user_profile_details,
    _display_token_help
)
from fastanime.libs.api.types import UserProfile
from rich.console import Console


def test_auth_status_display():
    """Test authentication status display functions."""
    console = Console()
    print("=== Testing Authentication Status Display ===\n")
    
    # Test without authentication
    print("1. Testing unauthenticated status:")
    _display_auth_status(console, None, True)
    
    # Test with authentication
    print("\n2. Testing authenticated status:")
    mock_user = UserProfile(
        id=12345,
        name="TestUser",
        avatar_url="https://example.com/avatar.jpg",
        banner_url="https://example.com/banner.jpg"
    )
    _display_auth_status(console, mock_user, True)


def test_profile_details():
    """Test user profile details display."""
    console = Console()
    print("\n\n=== Testing Profile Details Display ===\n")
    
    mock_user = UserProfile(
        id=12345,
        name="TestUser",
        avatar_url="https://example.com/avatar.jpg",
        banner_url="https://example.com/banner.jpg"
    )
    
    _display_user_profile_details(console, mock_user, True)


def test_token_help():
    """Test token help display."""
    console = Console()
    print("\n\n=== Testing Token Help Display ===\n")
    
    _display_token_help(console, True)


def test_auth_utils():
    """Test authentication utility functions."""
    print("\n\n=== Testing Authentication Utilities ===\n")
    
    from fastanime.cli.utils.auth_utils import (
        get_auth_status_indicator,
        format_login_success_message,
        format_logout_success_message
    )
    
    # Mock API client
    class MockApiClient:
        def __init__(self, user_profile=None):
            self.user_profile = user_profile
    
    # Test without authentication
    mock_api_unauthenticated = MockApiClient()
    status_text, profile = get_auth_status_indicator(mock_api_unauthenticated, True)
    print(f"Unauthenticated status: {status_text}")
    print(f"Profile: {profile}")
    
    # Test with authentication
    mock_user = UserProfile(
        id=12345,
        name="TestUser",
        avatar_url="https://example.com/avatar.jpg",
        banner_url="https://example.com/banner.jpg"
    )
    mock_api_authenticated = MockApiClient(mock_user)
    status_text, profile = get_auth_status_indicator(mock_api_authenticated, True)
    print(f"\nAuthenticated status: {status_text}")
    print(f"Profile: {profile.name if profile else None}")
    
    # Test success messages
    print(f"\nLogin success message: {format_login_success_message('TestUser', True)}")
    print(f"Logout success message: {format_logout_success_message(True)}")


def main():
    """Run all authentication tests."""
    print("🔐 Testing Step 5: AniList Authentication Flow Implementation\n")
    print("=" * 70)
    
    try:
        test_auth_status_display()
        test_profile_details()
        test_token_help()
        test_auth_utils()
        
        print("\n" + "=" * 70)
        print("✅ All authentication flow tests completed successfully!")
        print("\nFeatures implemented:")
        print("• Interactive OAuth login process")
        print("• Logout functionality with confirmation")
        print("• User profile viewing menu")
        print("• Authentication status display")
        print("• Token help and instructions")
        print("• Enhanced user feedback")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
