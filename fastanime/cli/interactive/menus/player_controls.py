import threading
from typing import TYPE_CHECKING, Callable, Dict

import click
from rich.console import Console

from ....libs.api.params import UpdateListEntryParams
from ..session import Context, session
from ..state import ControlFlow, State

if TYPE_CHECKING:
    from ....libs.providers.anime.types import Server


def _calculate_completion(start_time: str, end_time: str) -> float:
    """Calculates the percentage completion from two time strings (HH:MM:SS)."""
    try:
        start_parts = list(map(int, start_time.split(":")))
        end_parts = list(map(int, end_time.split(":")))
        start_secs = start_parts[0] * 3600 + start_parts[1] * 60 + start_parts[2]
        end_secs = end_parts[0] * 3600 + end_parts[1] * 60 + end_parts[2]
        return (start_secs / end_secs) * 100 if end_secs > 0 else 0
    except (ValueError, IndexError, ZeroDivisionError):
        return 0


def _update_progress_in_background(ctx: Context, anime_id: int, progress: int):
    """Fires off a non-blocking request to update AniList progress."""

    def task():
        # if not ctx.media_api.user_profile:
        #     return
        params = UpdateListEntryParams(media_id=anime_id, progress=progress)
        ctx.media_api.update_list_entry(params)
        # We don't need to show feedback here, it's a background task.

    threading.Thread(target=task).start()


@session.menu
def player_controls(ctx: Context, state: State) -> State | ControlFlow:
    """
    Handles post-playback options like playing the next episode,
    replaying, or changing streaming options.
    """
    # --- State and Context Extraction ---
    config = ctx.config
    player = ctx.player
    selector = ctx.selector
    console = Console()
    console.clear()

    provider_anime = state.provider.anime
    anilist_anime = state.media_api.anime
    current_episode_num = state.provider.episode_number
    selected_server = state.provider.selected_server
    all_servers = state.provider.servers
    player_result = state.provider.last_player_result

    if not all(
        (
            provider_anime,
            anilist_anime,
            current_episode_num,
            selected_server,
            all_servers,
        )
    ):
        console.print(
            "[bold red]Error: Player state is incomplete. Returning.[/bold red]"
        )
        return ControlFlow.BACK

    # --- Post-Playback Logic ---
    if player_result and player_result.stop_time and player_result.total_time:
        completion_pct = _calculate_completion(
            player_result.stop_time, player_result.total_time
        )
        if completion_pct >= config.stream.episode_complete_at:
            click.echo(
                f"[green]Episode {current_episode_num} marked as complete. Updating progress...[/green]"
            )
            _update_progress_in_background(
                ctx, anilist_anime.id, int(current_episode_num)
            )
            
            # Also update local watch history if enabled
            if config.stream.continue_from_watch_history and config.stream.preferred_watch_history == "local":
                from ...utils.watch_history_tracker import update_episode_progress
                try:
                    update_episode_progress(anilist_anime.id, int(current_episode_num), completion_pct)
                except (ValueError, AttributeError):
                    pass  # Skip if episode number conversion fails

    # --- Auto-Next Logic ---
    available_episodes = getattr(
        provider_anime.episodes, config.stream.translation_type, []
    )
    current_index = available_episodes.index(current_episode_num)

    if config.stream.auto_next and current_index < len(available_episodes) - 1:
        console.print("[cyan]Auto-playing next episode...[/cyan]")
        next_episode_num = available_episodes[current_index + 1]
        
        # Track next episode in watch history
        if config.stream.continue_from_watch_history and config.stream.preferred_watch_history == "local" and anilist_anime:
            from ...utils.watch_history_tracker import track_episode_viewing
            try:
                track_episode_viewing(anilist_anime, int(next_episode_num), start_tracking=True)
            except (ValueError, AttributeError):
                pass
        
        return State(
            menu_name="SERVERS",
            media_api=state.media_api,
            provider=state.provider.model_copy(
                update={"episode_number": next_episode_num}
            ),
        )

    # --- Action Definitions ---
    def next_episode() -> State | ControlFlow:
        if current_index < len(available_episodes) - 1:
            next_episode_num = available_episodes[current_index + 1]
            
            # Track next episode in watch history
            if config.stream.continue_from_watch_history and config.stream.preferred_watch_history == "local" and anilist_anime:
                from ...utils.watch_history_tracker import track_episode_viewing
                try:
                    track_episode_viewing(anilist_anime, int(next_episode_num), start_tracking=True)
                except (ValueError, AttributeError):
                    pass
            
            # Transition back to the SERVERS menu with the new episode number.
            return State(
                menu_name="SERVERS",
                media_api=state.media_api,
                provider=state.provider.model_copy(
                    update={"episode_number": next_episode_num}
                ),
            )
        console.print("[bold yellow]This is the last available episode.[/bold yellow]")
        return ControlFlow.CONTINUE

    def replay() -> State | ControlFlow:
        # We don't need to change state, just re-trigger the SERVERS menu's logic.
        return State(
            menu_name="SERVERS", media_api=state.media_api, provider=state.provider
        )

    def change_server() -> State | ControlFlow:
        server_map: Dict[str, Server] = {s.name: s for s in all_servers}
        new_server_name = selector.choose(
            "Select a different server:", list(server_map.keys())
        )
        if new_server_name:
            # Update the selected server and re-run the SERVERS logic.
            return State(
                menu_name="SERVERS",
                media_api=state.media_api,
                provider=state.provider.model_copy(
                    update={"selected_server": server_map[new_server_name]}
                ),
            )
        return ControlFlow.CONTINUE

    # --- Menu Options ---
    icons = config.general.icons
    options: Dict[str, Callable[[], State | ControlFlow]] = {}

    if current_index < len(available_episodes) - 1:
        options[f"{'⏭️ ' if icons else ''}Next Episode"] = next_episode

    options.update(
        {
            f"{'🔄 ' if icons else ''}Replay Episode": replay,
            f"{'💻 ' if icons else ''}Change Server": change_server,
            f"{'🎞️ ' if icons else ''}Back to Episode List": lambda: State(
                menu_name="EPISODES", media_api=state.media_api, provider=state.provider
            ),
            f"{'🏠 ' if icons else ''}Main Menu": lambda: State(menu_name="MAIN"),
            f"{'❌ ' if icons else ''}Exit": lambda: ControlFlow.EXIT,
        }
    )

    # --- Prompt and Execute ---
    header = f"Finished Episode {current_episode_num} of {provider_anime.title}"
    choice_str = selector.choose(
        prompt="What's next?", choices=list(options.keys()), header=header
    )

    if choice_str and choice_str in options:
        return options[choice_str]()

    return ControlFlow.BACK
