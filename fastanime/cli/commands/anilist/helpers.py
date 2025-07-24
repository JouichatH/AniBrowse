"""
Common helper functions for anilist subcommands.
"""

import json
from typing import TYPE_CHECKING, Optional

import click
from rich.progress import Progress

if TYPE_CHECKING:
    from fastanime.core.config import AppConfig
    from fastanime.libs.api.base import BaseApiClient
    from fastanime.libs.api.types import MediaSearchResult


def get_authenticated_api_client(config: "AppConfig") -> "BaseApiClient":
    """
    Get an authenticated API client or raise an error if not authenticated.

    Args:
        config: Application configuration

    Returns:
        Authenticated API client

    Raises:
        click.Abort: If user is not authenticated
    """
    from fastanime.cli.utils.feedback import create_feedback_manager
    from fastanime.libs.api.factory import create_api_client

    feedback = create_feedback_manager(config.general.icons)
    api_client = create_api_client(config.general.media_api, config)

    # Check if user is authenticated by trying to get viewer profile
    try:
        user_profile = api_client.get_viewer_profile()
        if not user_profile:
            feedback.error("Not authenticated", "Please run: fastanime anilist login")
            raise click.Abort()
    except Exception:
        feedback.error(
            "Authentication check failed", "Please run: fastanime anilist login"
        )
        raise click.Abort()

    return api_client


def handle_media_search_command(
    config: "AppConfig",
    dump_json: bool,
    task_name: str,
    search_params_factory,
    empty_message: str,
):
    """
    Generic handler for media search commands (trending, popular, recent, etc).

    Args:
        config: Application configuration
        dump_json: Whether to output JSON instead of launching interactive mode
        task_name: Name to display in progress indicator
        search_params_factory: Function that returns ApiSearchParams
        empty_message: Message to show when no results found
    """
    from fastanime.cli.utils.feedback import create_feedback_manager
    from fastanime.core.exceptions import FastAnimeError
    from fastanime.libs.api.factory import create_api_client

    feedback = create_feedback_manager(config.general.icons)

    try:
        # Create API client
        api_client = create_api_client(config.general.media_api, config)

        # Fetch media
        with Progress() as progress:
            progress.add_task(task_name, total=None)
            search_params = search_params_factory(config)
            search_result = api_client.search_media(search_params)

        if not search_result or not search_result.media:
            raise FastAnimeError(empty_message)

        if dump_json:
            # Use Pydantic's built-in serialization
            print(json.dumps(search_result.model_dump(), indent=2))
        else:
            # Launch interactive session for browsing results
            from fastanime.cli.interactive.session import session

            feedback.info(
                f"Found {len(search_result.media)} anime. Launching interactive mode..."
            )
            session.load_menus_from_folder()
            session.run(config)

    except FastAnimeError as e:
        feedback.error(f"Failed to fetch {task_name.lower()}", str(e))
        raise click.Abort()
    except Exception as e:
        feedback.error("Unexpected error occurred", str(e))
        raise click.Abort()


def handle_user_list_command(
    config: "AppConfig", dump_json: bool, status: str, list_name: str
):
    """
    Generic handler for user list commands (watching, completed, planning, etc).

    Args:
        config: Application configuration
        dump_json: Whether to output JSON instead of launching interactive mode
        status: The list status to fetch (CURRENT, COMPLETED, PLANNING, etc)
        list_name: Human-readable name for the list (e.g., "watching", "completed")
    """
    from fastanime.cli.utils.feedback import create_feedback_manager
    from fastanime.core.exceptions import FastAnimeError
    from fastanime.libs.api.params import UserMediaListSearchParams

    feedback = create_feedback_manager(config.general.icons)

    # Validate status parameter
    valid_statuses = [
        "CURRENT",
        "PLANNING",
        "COMPLETED",
        "DROPPED",
        "PAUSED",
        "REPEATING",
    ]
    if status not in valid_statuses:
        feedback.error(
            f"Invalid status: {status}", f"Valid statuses are: {valid_statuses}"
        )
        raise click.Abort()

    try:
        # Get authenticated API client
        api_client = get_authenticated_api_client(config)

        # Fetch user's anime list
        with Progress() as progress:
            progress.add_task(f"Fetching your {list_name} list...", total=None)
            list_params = UserMediaListSearchParams(
                status=status,  # type: ignore  # We validated it above
                page=1,
                per_page=config.anilist.per_page or 50,
            )
            user_list = api_client.search_media_list(list_params)

        if not user_list or not user_list.media:
            feedback.info(f"You have no anime in your {list_name} list")
            return

        if dump_json:
            # Use Pydantic's built-in serialization
            print(json.dumps(user_list.model_dump(), indent=2))
        else:
            # Launch interactive session for browsing results
            from fastanime.cli.interactive.session import session

            feedback.info(
                f"Found {len(user_list.media)} anime in your {list_name} list. Launching interactive mode..."
            )
            session.load_menus_from_folder()
            session.run(config)

    except FastAnimeError as e:
        feedback.error(f"Failed to fetch {list_name} list", str(e))
        raise click.Abort()
    except Exception as e:
        feedback.error("Unexpected error occurred", str(e))
        raise click.Abort()
