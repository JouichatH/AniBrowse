from typing import TYPE_CHECKING

import click
from rich.console import Console

from ..session import Context, session
from ..state import ControlFlow, ProviderState, State


@session.menu
def episodes(ctx: Context, state: State) -> State | ControlFlow:
    """
    Displays available episodes for a selected provider anime and handles
    the logic for continuing from watch history or manual selection.
    """
    provider_anime = state.provider.anime
    anilist_anime = state.media_api.anime
    config = ctx.config
    console = Console()
    console.clear()

    if not provider_anime or not anilist_anime:
        console.print("[bold red]Error: Anime details are missing.[/bold red]")
        return ControlFlow.BACK

    # Get the list of episode strings based on the configured translation type
    available_episodes = getattr(
        provider_anime.episodes, config.stream.translation_type, []
    )
    if not available_episodes:
        console.print(
            f"[bold yellow]No '{config.stream.translation_type}' episodes found for this anime.[/bold yellow]"
        )
        return ControlFlow.BACK

    chosen_episode: str | None = None

    if config.stream.continue_from_watch_history and False:
        progress = (
            anilist_anime.user_status.progress
            if anilist_anime.user_status and anilist_anime.user_status.progress
            else 0
        )

        # Calculate the next episode based on progress
        next_episode_num = str(progress + 1)

        if next_episode_num in available_episodes:
            click.echo(
                f"[cyan]Continuing from history. Auto-selecting episode {next_episode_num}.[/cyan]"
            )
            chosen_episode = next_episode_num
        else:
            # If the next episode isn't available, fall back to the last watched one
            last_watched_num = str(progress)
            if last_watched_num in available_episodes:
                click.echo(
                    f"[cyan]Next episode ({next_episode_num}) not found. Falling back to last watched episode {last_watched_num}.[/cyan]"
                )
                chosen_episode = last_watched_num
            else:
                click.echo(
                    f"[yellow]Could not find episode based on your watch history. Please select manually.[/yellow]"
                )

    if not chosen_episode:
        choices = [*sorted(available_episodes, key=float), "Back"]

        # TODO: Implement FZF/Rofi preview for episode thumbnails if available
        # preview_command = get_episode_preview(...)

        chosen_episode_str = ctx.selector.choose(
            prompt="Select Episode", choices=choices
        )

        if not chosen_episode_str or chosen_episode_str == "Back":
            return ControlFlow.BACK

        chosen_episode = chosen_episode_str

    return State(
        menu_name="SERVERS",
        media_api=state.media_api,
        provider=state.provider.model_copy(update={"episode_number": chosen_episode}),
    )
