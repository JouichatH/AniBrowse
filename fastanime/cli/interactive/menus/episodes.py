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

    if config.stream.continue_from_watch_history:
        # Use our new watch history system
        from ...utils.watch_history_tracker import get_continue_episode, track_episode_viewing
        
        # Try to get continue episode from watch history
        if config.stream.preferred_watch_history == "local":
            chosen_episode = get_continue_episode(anilist_anime, available_episodes, prefer_history=True)
            if chosen_episode:
                click.echo(
                    f"[cyan]Continuing from local watch history. Auto-selecting episode {chosen_episode}.[/cyan]"
                )
        
        # Fallback to AniList progress if local history doesn't have info or preference is remote
        if not chosen_episode and config.stream.preferred_watch_history == "remote":
            progress = (
                anilist_anime.user_status.progress
                if anilist_anime.user_status and anilist_anime.user_status.progress
                else 0
            )

            # Calculate the next episode based on progress
            next_episode_num = str(progress + 1)

            if next_episode_num in available_episodes:
                click.echo(
                    f"[cyan]Continuing from AniList history. Auto-selecting episode {next_episode_num}.[/cyan]"
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

        # Get episode preview command if preview is enabled
        preview_command = None
        if ctx.config.general.preview != "none":
            from ...utils.previews import get_episode_preview
            preview_command = get_episode_preview(available_episodes, anilist_anime, ctx.config)

        chosen_episode_str = ctx.selector.choose(
            prompt="Select Episode", 
            choices=choices,
            preview=preview_command
        )

        if not chosen_episode_str or chosen_episode_str == "Back":
            return ControlFlow.BACK

        chosen_episode = chosen_episode_str

    # Track episode selection in watch history (if enabled in config)
    if config.stream.continue_from_watch_history and config.stream.preferred_watch_history == "local":
        from ...utils.watch_history_tracker import track_episode_viewing
        try:
            episode_num = int(chosen_episode)
            track_episode_viewing(anilist_anime, episode_num, start_tracking=True)
        except (ValueError, AttributeError):
            pass  # Skip tracking if episode number is invalid

    return State(
        menu_name="SERVERS",
        media_api=state.media_api,
        provider=state.provider.model_copy(update={"episode_number": chosen_episode}),
    )
