"""
Authentication utilities for the interactive CLI.
Provides functions to check authentication status and display user information.
"""

from typing import Optional

from ...libs.api.base import BaseApiClient
from ...libs.api.types import UserProfile
from .feedback import FeedbackManager


def get_auth_status_indicator(
    api_client: BaseApiClient, icons_enabled: bool = True
) -> tuple[str, Optional[UserProfile]]:
    """
    Get authentication status indicator for display in menus.

    Returns:
        tuple of (status_text, user_profile or None)
    """
    user_profile = getattr(api_client, "user_profile", None)

    if user_profile:
        # User is authenticated
        icon = "🟢 " if icons_enabled else "● "
        status_text = f"{icon}Logged in as {user_profile.name}"
        return status_text, user_profile
    else:
        # User is not authenticated
        icon = "🔴 " if icons_enabled else "○ "
        status_text = f"{icon}Not logged in"
        return status_text, None


def format_user_info_header(
    user_profile: Optional[UserProfile], icons_enabled: bool = True
) -> str:
    """
    Format user information for display in menu headers.

    Returns:
        Formatted string with user info or empty string if not authenticated
    """
    if not user_profile:
        return ""

    icon = "👤 " if icons_enabled else ""
    return f"{icon}User: {user_profile.name} (ID: {user_profile.id})"


def check_authentication_required(
    api_client: BaseApiClient,
    feedback: FeedbackManager,
    operation_name: str = "this action",
) -> bool:
    """
    Check if user is authenticated and show appropriate feedback if not.

    Returns:
        True if authenticated, False if not (with feedback shown)
    """
    user_profile = getattr(api_client, "user_profile", None)

    if not user_profile:
        feedback.warning(
            f"Authentication required for {operation_name}",
            "Please log in to your AniList account using 'fastanime anilist auth' to access this feature",
        )
        return False

    return True


def format_auth_menu_header(
    api_client: BaseApiClient, base_header: str, icons_enabled: bool = True
) -> str:
    """
    Format menu header with authentication status.

    Args:
        api_client: The API client to check authentication status
        base_header: Base header text (e.g., "FastAnime Main Menu")
        icons_enabled: Whether to show icons

    Returns:
        Formatted header with authentication status
    """
    status_text, user_profile = get_auth_status_indicator(api_client, icons_enabled)

    if user_profile:
        return f"{base_header}\n{status_text}"
    else:
        return f"{base_header}\n{status_text} - Some features require authentication"


def prompt_for_authentication(
    feedback: FeedbackManager, operation_name: str = "continue"
) -> bool:
    """
    Prompt user about authentication requirement and offer guidance.

    Returns:
        True if user wants to continue anyway, False if they want to stop
    """
    feedback.info(
        "Authentication Required",
        f"To {operation_name}, you need to log in to your AniList account",
    )

    feedback.info(
        "How to authenticate:",
        "Run 'fastanime anilist auth' in your terminal to log in",
    )

    return feedback.confirm("Continue without authentication?", default=False)


def show_authentication_instructions(feedback: FeedbackManager, icons_enabled: bool = True) -> None:
    """
    Show detailed instructions for authenticating with AniList.
    """
    icon = "🔐 " if icons_enabled else ""
    
    feedback.info(
        f"{icon}AniList Authentication Required",
        "To access personalized features, you need to authenticate with your AniList account"
    )
    
    instructions = [
        "1. Go to the interactive menu: 'Authentication' option",
        "2. Select 'Login to AniList'",
        "3. Follow the OAuth flow in your browser",
        "4. Copy and paste the token when prompted",
        "",
        "Alternatively, use the CLI command:",
        "fastanime anilist auth"
    ]
    
    for instruction in instructions:
        if instruction:
            feedback.info("", instruction)
        else:
            feedback.info("", "")


def get_authentication_prompt_message(operation_name: str, icons_enabled: bool = True) -> str:
    """
    Get a formatted message prompting for authentication for a specific operation.
    """
    icon = "🔒 " if icons_enabled else ""
    return f"{icon}Authentication required to {operation_name}. Please log in to continue."


def format_login_success_message(user_name: str, icons_enabled: bool = True) -> str:
    """
    Format a success message for successful login.
    """
    icon = "🎉 " if icons_enabled else ""
    return f"{icon}Successfully logged in as {user_name}!"


def format_logout_success_message(icons_enabled: bool = True) -> str:
    """
    Format a success message for successful logout.
    """
    icon = "👋 " if icons_enabled else ""
    return f"{icon}Successfully logged out!"
