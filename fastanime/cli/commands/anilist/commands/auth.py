import click

from .....core.config.model import AppConfig


@click.command(help="Login to your AniList account to enable progress tracking.")
@click.option("--status", "-s", is_flag=True, help="Check current login status.")
@click.option("--logout", "-l", is_flag=True, help="Log out and erase credentials.")
@click.pass_obj
def auth(config: AppConfig, status: bool, logout: bool):
    """Handles user authentication and credential management."""
    from .....core.constants import ANILIST_AUTH
    from .....libs.media_api.api import create_api_client
    from .....libs.selectors.selector import create_selector
    from ....service.auth import AuthService
    from ....service.feedback import FeedbackService

    auth_service = AuthService("anilist")
    feedback = FeedbackService(config)
    selector = create_selector(config)
    feedback.clear_console()

    if status:
        user_data = auth_service.get_auth()
        if user_data:
            feedback.info(f"Logged in as: {user_data.user_profile}")
        else:
            feedback.error("Not logged in.")
        return

    if logout:
        if selector.confirm("Are you sure you want to log out and erase your token?"):
            auth_service.clear_user_profile()
            feedback.info("You have been logged out.")
        return

    if auth_profile := auth_service.get_auth():
        if not selector.confirm(
            f"You are already logged in as {auth_profile.user_profile.name}.Would you like to relogin"
        ):
            return
    api_client = create_api_client("anilist", config)

    # TODO: stop the printing of opening browser session to stderr
    click.launch(ANILIST_AUTH)
    feedback.info("Your browser has been opened to obtain an AniList token.")
    feedback.info(
        "After authorizing, copy the token from the address bar and paste it below."
    )

    token = selector.ask("Enter your AniList Access Token")
    if not token:
        feedback.error("Login cancelled.")
        return

    # Use the API client to validate the token and get profile info
    profile = api_client.authenticate(token.strip())

    if profile:
        # If successful, use the manager to save the credentials
        auth_service.save_user_profile(profile, token)
        feedback.info(f"Successfully logged in as {profile.name}! ✨")
    else:
        feedback.error("Login failed. The token may be invalid or expired.")
