import threading
from typing import TYPE_CHECKING, Callable, Dict

import click
from rich.console import Console

from ..session import Context, session
from ..state import ControlFlow, State

if TYPE_CHECKING:
    from ....libs.providers.anime.types import Server


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

    # --- Auto-Next Logic ---
    available_episodes = getattr(
        provider_anime.episodes, config.stream.translation_type, []
    )
    current_index = available_episodes.index(current_episode_num)

    if config.stream.auto_next and current_index < len(available_episodes) - 1:
        console.print("[cyan]Auto-playing next episode...[/cyan]")
        next_episode_num = available_episodes[current_index + 1]

        # Track next episode in unified media registry

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
