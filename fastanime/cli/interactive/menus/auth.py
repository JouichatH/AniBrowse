"""
Interactive authentication menu for AniList OAuth login/logout and user profile management.
Implements Step 5: AniList Authentication Flow
"""

import webbrowser
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ....libs.api.types import UserProfile
from ...auth.manager import AuthManager
from ...utils.feedback import create_feedback_manager, execute_with_feedback
from ..session import Context, session
from ..state import InternalDirective, State


@session.menu
def auth(ctx: Context, state: State) -> State | InternalDirective:
    """
    Interactive authentication menu for managing AniList login/logout and viewing user profile.
    """
    icons = ctx.config.general.icons
    feedback = create_feedback_manager(icons)
    console = Console()
    console.clear()

    # Get current authentication status
    user_profile = getattr(ctx.media_api, "user_profile", None)
    auth_manager = AuthManager()

    # Display current authentication status
    _display_auth_status(console, user_profile, icons)

    # Menu options based on authentication status
    if user_profile:
        options = [
            f"{'👤 ' if icons else ''}View Profile Details",
            f"{'🔓 ' if icons else ''}Logout",
            f"{'↩️ ' if icons else ''}Back to Main Menu",
        ]
    else:
        options = [
            f"{'🔐 ' if icons else ''}Login to AniList",
            f"{'❓ ' if icons else ''}How to Get Token",
            f"{'↩️ ' if icons else ''}Back to Main Menu",
        ]

    choice = ctx.selector.choose(
        prompt="Select Authentication Action",
        choices=options,
        header="AniList Authentication Menu",
    )

    if not choice:
        return InternalDirective.BACK

    # Handle menu choices
    if "Login to AniList" in choice:
        return _handle_login(ctx, auth_manager, feedback, icons)
    elif "Logout" in choice:
        return _handle_logout(ctx, auth_manager, feedback, icons)
    elif "View Profile Details" in choice:
        _display_user_profile_details(console, user_profile, icons)
        feedback.pause_for_user("Press Enter to continue")
        return InternalDirective.RELOAD
    elif "How to Get Token" in choice:
        _display_token_help(console, icons)
        feedback.pause_for_user("Press Enter to continue")
        return InternalDirective.RELOAD
    else:  # Back to Main Menu
        return InternalDirective.BACK


def _display_auth_status(
    console: Console, user_profile: Optional[UserProfile], icons: bool
):
    """Display current authentication status in a nice panel."""
    if user_profile:
        status_icon = "🟢" if icons else "[green]●[/green]"
        status_text = f"{status_icon} Authenticated"
        user_info = f"Logged in as: [bold cyan]{user_profile.name}[/bold cyan]\nUser ID: {user_profile.id}"
    else:
        status_icon = "🔴" if icons else "[red]○[/red]"
        status_text = f"{status_icon} Not Authenticated"
        user_info = "Log in to access personalized features like:\n• Your anime lists (Watching, Completed, etc.)\n• Progress tracking\n• List management"

    panel = Panel(
        user_info,
        title=f"Authentication Status: {status_text}",
        border_style="green" if user_profile else "red",
    )
    console.print(panel)
    console.print()


def _handle_login(
    ctx: Context, auth_manager: AuthManager, feedback, icons: bool
) -> State | InternalDirective:
    """Handle the interactive login process."""

    def perform_login():
        # Open browser to AniList OAuth page
        oauth_url = "https://anilist.co/api/v2/oauth/authorize?client_id=20148&response_type=token"

        if feedback.confirm(
            "Open AniList authorization page in browser?", default=True
        ):
            try:
                webbrowser.open(oauth_url)
                feedback.info(
                    "Browser opened",
                    "Complete the authorization process in your browser",
                )
            except Exception as e:
                feedback.warning(
                    "Could not open browser automatically",
                    f"Please manually visit: {oauth_url}",
                )
        else:
            feedback.info("Manual authorization", f"Please visit: {oauth_url}")

        # Get token from user
        feedback.info(
            "Token Input", "Paste the token from the browser URL after '#access_token='"
        )
        token = ctx.selector.ask("Enter your AniList Access Token")

        if not token or not token.strip():
            feedback.error("Login cancelled", "No token provided")
            return None

        # Authenticate with the API
        profile = ctx.media_api.authenticate(token.strip())

        if not profile:
            feedback.error(
                "Authentication failed", "The token may be invalid or expired"
            )
            return None

        # Save credentials using the auth manager
        auth_manager.save_user_profile(profile, token.strip())
        return profile

    success, profile = execute_with_feedback(
        perform_login,
        feedback,
        "authenticate",
        loading_msg="Validating token with AniList",
        success_msg=f"Successfully logged in! 🎉"
        if icons
        else f"Successfully logged in!",
        error_msg="Login failed",
        show_loading=True,
    )

    if success and profile:
        feedback.success(
            f"Logged in as {profile.name}" if profile else "Successfully logged in"
        )
        feedback.pause_for_user("Press Enter to continue")

    return InternalDirective.RELOAD


def _handle_logout(
    ctx: Context, auth_manager: AuthManager, feedback, icons: bool
) -> State | InternalDirective:
    """Handle the logout process with confirmation."""
    if not feedback.confirm(
        "Are you sure you want to logout?",
        "This will remove your saved AniList token and log you out",
        default=False,
    ):
        return InternalDirective.RELOAD

    def perform_logout():
        # Clear from auth manager
        if hasattr(auth_manager, "logout"):
            auth_manager.logout()
        else:
            auth_manager.clear_user_profile()

        # Clear from API client
        ctx.media_api.token = None
        ctx.media_api.user_profile = None
        if hasattr(ctx.media_api, "http_client"):
            ctx.media_api.http_client.headers.pop("Authorization", None)

        return True

    success, _ = execute_with_feedback(
        perform_logout,
        feedback,
        "logout",
        loading_msg="Logging out",
        success_msg="Successfully logged out 👋"
        if icons
        else "Successfully logged out",
        error_msg="Logout failed",
        show_loading=False,
    )

    if success:
        feedback.pause_for_user("Press Enter to continue")

    return InternalDirective.CONFIG_EDIT


def _display_user_profile_details(
    console: Console, user_profile: UserProfile, icons: bool
):
    """Display detailed user profile information."""
    if not user_profile:
        console.print("[red]No user profile available[/red]")
        return

    # Create a detailed profile table
    table = Table(title=f"{'👤 ' if icons else ''}User Profile: {user_profile.name}")
    table.add_column("Property", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    table.add_row("Name", user_profile.name)
    table.add_row("User ID", str(user_profile.id))

    if user_profile.avatar_url:
        table.add_row("Avatar URL", user_profile.avatar_url)

    if user_profile.banner_url:
        table.add_row("Banner URL", user_profile.banner_url)

    console.print()
    console.print(table)
    console.print()

    # Show available features
    features_panel = Panel(
        "Available Features:\n"
        f"{'📺 ' if icons else '• '}Access your anime lists (Watching, Completed, etc.)\n"
        f"{'✏️ ' if icons else '• '}Update watch progress and scores\n"
        f"{'➕ ' if icons else '• '}Add/remove anime from your lists\n"
        f"{'🔄 ' if icons else '• '}Sync progress with AniList\n"
        f"{'🔔 ' if icons else '• '}Access AniList notifications",
        title="Available with Authentication",
        border_style="green",
    )
    console.print(features_panel)


def _display_token_help(console: Console, icons: bool):
    """Display help information about getting an AniList token."""
    help_text = """
[bold cyan]How to get your AniList Access Token:[/bold cyan]

[bold]Step 1:[/bold] Visit the AniList authorization page
https://anilist.co/api/v2/oauth/authorize?client_id=20148&response_type=token

[bold]Step 2:[/bold] Log in to your AniList account if prompted

[bold]Step 3:[/bold] Click "Authorize" to grant FastAnime access

[bold]Step 4:[/bold] Copy the token from the browser URL
Look for the part after "#access_token=" in the address bar

[bold]Step 5:[/bold] Paste the token when prompted in FastAnime

[yellow]Note:[/yellow] The token will be stored securely and used for all AniList features.
You only need to do this once unless you revoke access or the token expires.

[yellow]Privacy:[/yellow] FastAnime only requests minimal permissions needed for 
list management and does not access sensitive account information.
"""

    panel = Panel(
        help_text,
        title=f"{'❓ ' if icons else ''}AniList Token Help",
        border_style="blue",
    )
    console.print()
    console.print(panel)
