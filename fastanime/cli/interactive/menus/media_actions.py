from typing import TYPE_CHECKING, Callable, Dict, Tuple

import click
from InquirerPy.validator import EmptyInputValidator, NumberValidator

from ....libs.api.params import UpdateListEntryParams
from ....libs.api.types import UserListStatusType
from ...utils.anilist import anilist_data_helper
from ..session import Context, session
from ..state import ControlFlow, MediaApiState, ProviderState, State

if TYPE_CHECKING:
    from ....libs.api.types import MediaItem


@session.menu
def media_actions(ctx: Context, state: State) -> State | ControlFlow:
    """
    Displays actions for a single, selected anime, such as streaming,
    viewing details, or managing its status on the user's list.
    """
    anime = state.media_api.anime
    if not anime:
        click.echo("[bold red]Error: No anime selected.[/bold red]")
        return ControlFlow.BACK

    icons = ctx.config.general.icons
    selector = ctx.selector
    player = ctx.player

    # --- Action Implementations ---
    def stream() -> State | ControlFlow:
        # This is the key transition to the provider-focused part of the app.
        # We create a new state for the next menu, carrying over the selected
        # anime's details for the provider to use.
        return State(
            menu_name="PROVIDER_SEARCH",
            media_api=state.media_api,  # Carry over the existing api state
            provider=ProviderState(),  # Initialize a fresh provider state
        )

    def watch_trailer() -> State | ControlFlow:
        if not anime.trailer or not anime.trailer.id:
            click.echo(
                "[bold yellow]No trailer available for this anime.[/bold yellow]"
            )
        else:
            trailer_url = f"https://www.youtube.com/watch?v={anime.trailer.id}"
            click.echo(
                f"Playing trailer for '{anime.title.english or anime.title.romaji}'..."
            )
            player.play(url=trailer_url, title=f"Trailer: {anime.title.english}")
        return ControlFlow.CONTINUE

    def add_to_list() -> State | ControlFlow:
        choices = ["CURRENT", "PLANNING", "COMPLETED", "DROPPED", "PAUSED", "REPEATING"]
        status = selector.choose("Select list status:", choices=choices)
        if status:
            _update_user_list(
                ctx,
                anime,
                UpdateListEntryParams(media_id=anime.id, status=status),
            )
        return ControlFlow.CONTINUE

    def score_anime() -> State | ControlFlow:
        score_str = selector.ask(
            "Enter score (0.0 - 10.0):",
        )
        try:
            score = float(score_str) if score_str else 0.0
            if not 0.0 <= score <= 10.0:
                raise ValueError("Score out of range.")
            _update_user_list(
                ctx, anime, UpdateListEntryParams(media_id=anime.id, score=score)
            )
        except (ValueError, TypeError):
            click.echo(
                "[bold red]Invalid score. Please enter a number between 0 and 10.[/bold red]"
            )
        return ControlFlow.CONTINUE

    def view_info() -> State | ControlFlow:
        # Placeholder for a more detailed info screen if needed.
        # For now, we'll just print key details.
        from rich import box
        from rich.panel import Panel
        from rich.text import Text

        title = Text(anime.title.english or anime.title.romaji, style="bold cyan")
        description = anilist_data_helper.clean_html(
            anime.description or "No description."
        )
        genres = f"[bold]Genres:[/bold] {', '.join(anime.genres)}"

        panel_content = f"{genres}\n\n{description}"

        click.echo(Panel(panel_content, title=title, box=box.ROUNDED, expand=False))
        selector.ask("Press Enter to continue...")  # Pause to allow reading
        return ControlFlow.CONTINUE

    # --- Build Menu Options ---
    options: Dict[str, Callable[[], State | ControlFlow]] = {
        f"{'▶️ ' if icons else ''}Stream": stream,
        f"{'📼 ' if icons else ''}Watch Trailer": watch_trailer,
        f"{'➕ ' if icons else ''}Add/Update List": add_to_list,
        f"{'⭐ ' if icons else ''}Score Anime": score_anime,
        f"{'ℹ️ ' if icons else ''}View Info": view_info,
        # TODO: Add 'Recommendations' and 'Relations' here later.
        f"{'🔙 ' if icons else ''}Back to Results": lambda: ControlFlow.BACK,
    }

    # --- Prompt and Execute ---
    header = f"Actions for: {anime.title.english or anime.title.romaji}"
    choice_str = ctx.selector.choose(
        prompt="Select Action", choices=list(options.keys()), header=header
    )

    if choice_str and choice_str in options:
        return options[choice_str]()

    return ControlFlow.BACK


def _update_user_list(ctx: Context, anime: MediaItem, params: UpdateListEntryParams):
    """Helper to call the API to update a user's list and show feedback."""
    if not ctx.media_api.user_profile:
        click.echo("[bold yellow]You must be logged in to modify your list.[/]")
        return

    success = ctx.media_api.update_list_entry(params)
    if success:
        click.echo(
            f"[bold green]Successfully updated '{anime.title.english or anime.title.romaji}' on your list![/]"
        )
    else:
        click.echo("[bold red]Failed to update list entry.[/bold red]")
