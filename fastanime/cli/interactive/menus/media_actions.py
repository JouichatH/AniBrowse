from typing import Callable, Dict

import click
from rich.console import Console

from ....libs.api.params import UpdateListEntryParams
from ....libs.api.types import MediaItem
from ....libs.players.params import PlayerParams
from ...utils.feedback import create_feedback_manager, execute_with_feedback
from ...utils.auth.utils import check_authentication_required, get_auth_status_indicator
from ..session import Context, session
from ..state import ControlFlow, ProviderState, State

MenuAction = Callable[[], State | ControlFlow]


@session.menu
def media_actions(ctx: Context, state: State) -> State | ControlFlow:
    """
    Displays actions for a single, selected anime, such as streaming,
    viewing details, or managing its status on the user's list.
    """
    icons = ctx.config.general.icons

    # Get authentication status for display
    auth_status, user_profile = get_auth_status_indicator(ctx.media_api, icons)

    # Create header with auth status
    anime = state.media_api.anime
    anime_title = anime.title.english or anime.title.romaji if anime else "Unknown"
    header = f"Actions for: {anime_title}\n{auth_status}"

    # TODO: Add 'Recommendations' and 'Relations' here later.
    options: Dict[str, MenuAction] = {
        f"{'▶️ ' if icons else ''}Stream": _stream(ctx, state),
        f"{'📼 ' if icons else ''}Watch Trailer": _watch_trailer(ctx, state),
        f"{'➕ ' if icons else ''}Add/Update List": _add_to_list(ctx, state),
        f"{'⭐ ' if icons else ''}Score Anime": _score_anime(ctx, state),
        f"{'� ' if icons else ''}Manage in Lists": _manage_in_lists(ctx, state),
        f"{'�📚 ' if icons else ''}Add to Local History": _add_to_local_history(ctx, state),
        f"{'ℹ️ ' if icons else ''}View Info": _view_info(ctx, state),
        f"{'🔙 ' if icons else ''}Back to Results": lambda: ControlFlow.BACK,
    }

    # --- Prompt and Execute ---
    choice_str = ctx.selector.choose(
        prompt="Select Action", choices=list(options.keys()), header=header
    )

    if choice_str and choice_str in options:
        return options[choice_str]()

    return ControlFlow.BACK


# --- Action Implementations ---
def _stream(ctx: Context, state: State) -> MenuAction:
    def action():
        return State(
            menu_name="PROVIDER_SEARCH",
            media_api=state.media_api,  # Carry over the existing api state
            provider=ProviderState(),  # Initialize a fresh provider state
        )

    return action


def _watch_trailer(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = create_feedback_manager(ctx.config.general.icons)
        anime = state.media_api.anime
        if not anime:
            return ControlFlow.CONTINUE
        if not anime.trailer or not anime.trailer.id:
            feedback.warning(
                "No trailer available for this anime",
                "This anime doesn't have a trailer link in the database",
            )
        else:
            trailer_url = f"https://www.youtube.com/watch?v={anime.trailer.id}"

            def play_trailer():
                ctx.player.play(PlayerParams(url=trailer_url, title=""))

            execute_with_feedback(
                play_trailer,
                feedback,
                "play trailer",
                loading_msg=f"Playing trailer for '{anime.title.english or anime.title.romaji}'",
                success_msg="Trailer started successfully",
                show_loading=False,
            )
        return ControlFlow.CONTINUE

    return action


def _add_to_list(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = create_feedback_manager(ctx.config.general.icons)
        anime = state.media_api.anime
        if not anime:
            return ControlFlow.CONTINUE

        # Check authentication before proceeding
        if not check_authentication_required(
            ctx.media_api, feedback, "add anime to your list"
        ):
            return ControlFlow.CONTINUE

        choices = ["CURRENT", "PLANNING", "COMPLETED", "DROPPED", "PAUSED", "REPEATING"]
        status = ctx.selector.choose("Select list status:", choices=choices)
        if status:
            # status is now guaranteed to be one of the valid choices
            _update_user_list_with_feedback(
                ctx,
                anime,
                UpdateListEntryParams(media_id=anime.id, status=status),  # type: ignore
                feedback,
            )
        return ControlFlow.CONTINUE

    return action


def _score_anime(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = create_feedback_manager(ctx.config.general.icons)
        anime = state.media_api.anime
        if not anime:
            return ControlFlow.CONTINUE

        # Check authentication before proceeding
        if not check_authentication_required(ctx.media_api, feedback, "score anime"):
            return ControlFlow.CONTINUE

        score_str = ctx.selector.ask("Enter score (0.0 - 10.0):")
        try:
            score = float(score_str) if score_str else 0.0
            if not 0.0 <= score <= 10.0:
                raise ValueError("Score out of range.")
            _update_user_list_with_feedback(
                ctx,
                anime,
                UpdateListEntryParams(media_id=anime.id, score=score),
                feedback,
            )
        except (ValueError, TypeError):
            feedback.error(
                "Invalid score entered", "Please enter a number between 0.0 and 10.0"
            )
        return ControlFlow.CONTINUE

    return action


def _view_info(ctx: Context, state: State) -> MenuAction:
    def action():
        anime = state.media_api.anime
        if not anime:
            return ControlFlow.CONTINUE
        # Placeholder for a more detailed info screen if needed.
        # For now, we'll just print key details.
        from rich import box
        from rich.panel import Panel
        from rich.text import Text

        from ...utils import image

        console = Console()
        title = Text(anime.title.english or anime.title.romaji or "", style="bold cyan")
        description = Text(anime.description or "NO description")
        genres = Text(f"Genres: {', '.join(anime.genres)}")

        panel_content = f"{genres}\n\n{description}"

        console.clear()
        if cover_image := anime.cover_image:
            image.render_image(cover_image.large)

        console.print(Panel(panel_content, title=title, box=box.ROUNDED, expand=True))
        ctx.selector.ask("Press Enter to continue...")
        return ControlFlow.CONTINUE

    return action


def _update_user_list(ctx: Context, anime: MediaItem, params: UpdateListEntryParams):
    """Helper to call the API to update a user's list and show feedback."""
    # if not ctx.media_api.user_profile:
    #     click.echo("[bold yellow]You must be logged in to modify your list.[/]")
    #     return

    success = ctx.media_api.update_list_entry(params)
    if success:
        click.echo(
            f"[bold green]Successfully updated '{anime.title.english or anime.title.romaji}' on your list![/]"
        )
    else:
        click.echo("[bold red]Failed to update list entry.[/bold red]")


def _update_user_list_with_feedback(
    ctx: Context, anime: MediaItem, params: UpdateListEntryParams, feedback
):
    """Helper to call the API to update a user's list with comprehensive feedback."""
    # Authentication check is handled by the calling functions now
    # This function assumes authentication has already been verified

    def update_operation():
        return ctx.media_api.update_list_entry(params)

    anime_title = anime.title.english or anime.title.romaji
    success, result = execute_with_feedback(
        update_operation,
        feedback,
        "update anime list",
        loading_msg=f"Updating '{anime_title}' on your list",
        success_msg=f"Successfully updated '{anime_title}' on your list!",
        error_msg="Failed to update list entry",
        show_loading=False,
    )


def _add_to_local_history(ctx: Context, state: State) -> MenuAction:
    """Add anime to local watch history with status selection."""
    
    def action() -> State | ControlFlow:
        anime = state.media_api.anime
        if not anime:
            click.echo("[bold red]No anime data available.[/bold red]")
            return ControlFlow.CONTINUE
        
        feedback = create_feedback_manager(ctx.config.general.icons)
        
        # Check if already in watch history
        from ...utils.watch_history_manager import WatchHistoryManager
        history_manager = WatchHistoryManager()
        existing_entry = history_manager.get_entry(anime.id)
        
        if existing_entry:
            # Ask if user wants to update existing entry
            if not feedback.confirm(f"'{existing_entry.get_display_title()}' is already in your local watch history. Update it?"):
                return ControlFlow.CONTINUE
        
        # Status selection
        statuses = ["watching", "completed", "planning", "paused", "dropped"]
        status_choices = [status.title() for status in statuses]
        
        chosen_status = ctx.selector.choose(
            "Select status for local watch history:",
            choices=status_choices + ["Cancel"]
        )
        
        if not chosen_status or chosen_status == "Cancel":
            return ControlFlow.CONTINUE
        
        status = chosen_status.lower()
        
        # Episode number if applicable
        episode = 0
        if status in ["watching", "completed"]:
            if anime.episodes and anime.episodes > 1:
                episode_str = ctx.selector.ask(f"Enter current episode (1-{anime.episodes}, default: 0):")
                try:
                    episode = int(episode_str) if episode_str else 0
                    episode = max(0, min(episode, anime.episodes))
                except ValueError:
                    episode = 0
        
        # Mark as completed if status is completed
        if status == "completed" and anime.episodes:
            episode = anime.episodes
        
        # Add to watch history
        from ...utils.watch_history_tracker import watch_tracker
        success = watch_tracker.add_anime_to_history(anime, status)
        
        if success and episode > 0:
            # Update episode progress
            history_manager.mark_episode_watched(anime.id, episode, 1.0 if status == "completed" else 0.0)
        
        if success:
            feedback.success(f"Added '{anime.title.english or anime.title.romaji}' to local watch history with status: {status}")
        else:
            feedback.error("Failed to add anime to local watch history")
        
        return ControlFlow.CONTINUE
    
    return action


def _manage_in_lists(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = create_feedback_manager(ctx.config.general.icons)
        anime = state.media_api.anime
        if not anime:
            return ControlFlow.CONTINUE

        # Check authentication before proceeding
        if not check_authentication_required(
            ctx.media_api, feedback, "manage anime in your lists"
        ):
            return ControlFlow.CONTINUE

        # Navigate to AniList anime details with this specific anime
        return State(
            menu_name="ANILIST_ANIME_DETAILS",
            data={
                "anime": anime,
                "list_status": "CURRENT",  # Default status, will be updated when loaded
                "return_page": 1,
                "from_media_actions": True  # Flag to return here instead of lists
            }
        )

    return action
