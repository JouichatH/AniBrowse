from typing import Dict, List

from rich.console import Console
from rich.progress import Progress

from ....libs.players.params import PlayerParams
from ....libs.providers.anime.params import EpisodeStreamsParams
from ....libs.providers.anime.types import Server
from ..session import Context, session
from ..state import InternalDirective, State


def _filter_by_quality(links, quality):
    # Simplified version of your filter_by_quality for brevity
    for link in links:
        if str(link.quality) == quality:
            return link
    return links[0] if links else None


@session.menu
def servers(ctx: Context, state: State) -> State | InternalDirective:
    """
    Fetches and displays available streaming servers for a chosen episode,
    then launches the media player and transitions to post-playback controls.
    """
    provider_anime = state.provider.anime
    if not state.media_api.anime:
        return InternalDirective.BACK
    anime_title = (
        state.media_api.anime.title.romaji or state.media_api.anime.title.english
    )
    episode_number = state.provider.episode_number
    config = ctx.config
    provider = ctx.provider
    selector = ctx.selector
    console = Console()
    console.clear()

    if not provider_anime or not episode_number:
        console.print(
            "[bold red]Error: Anime or episode details are missing.[/bold red]"
        )
        selector.ask("Enter to continue...")
        return InternalDirective.BACK

    # --- Fetch Server Streams ---
    with Progress(transient=True) as progress:
        progress.add_task(
            f"[cyan]Fetching servers for episode {episode_number}...", total=None
        )
        server_iterator = provider.episode_streams(
            EpisodeStreamsParams(
                anime_id=provider_anime.id,
                query=anime_title,
                episode=episode_number,
                translation_type=config.stream.translation_type,
            )
        )
        # Consume the iterator to get a list of all servers
        all_servers: List[Server] = list(server_iterator) if server_iterator else []

    if not all_servers:
        console.print(
            f"[bold yellow]No streaming servers found for this episode.[/bold yellow]"
        )
        return InternalDirective.BACK

    # --- Auto-Select or Prompt for Server ---
    server_map: Dict[str, Server] = {s.name: s for s in all_servers}
    selected_server: Server | None = None

    preferred_server = config.stream.server.value.lower()
    if preferred_server == "top":
        selected_server = all_servers[0]
        console.print(f"[cyan]Auto-selecting top server:[/] {selected_server.name}")
    elif preferred_server in server_map:
        selected_server = server_map[preferred_server]
        console.print(
            f"[cyan]Auto-selecting preferred server:[/] {selected_server.name}"
        )
    else:
        choices = [*server_map.keys(), "Back"]
        chosen_name = selector.choose("Select Server", choices)
        if not chosen_name or chosen_name == "Back":
            return InternalDirective.BACK
        selected_server = server_map[chosen_name]

    stream_link_obj = _filter_by_quality(selected_server.links, config.stream.quality)
    if not stream_link_obj:
        console.print(
            f"[bold red]No stream of quality '{config.stream.quality}' found on server '{selected_server.name}'.[/bold red]"
        )
        return InternalDirective.RELOAD

    # --- Launch Player ---
    final_title = f"{provider_anime.title} - Ep {episode_number}"
    console.print(f"[bold green]Launching player for:[/] {final_title}")

    player_result = ctx.player.play(
        PlayerParams(
            url=stream_link_obj.link,
            title=final_title,
            subtitles=[sub.url for sub in selected_server.subtitles],
            headers=selected_server.headers,
        )
    )
    if state.media_api.anime and state.provider.episode_number:
        ctx.services.watch_history.track(
            state.media_api.anime, state.provider.episode_number, player_result
        )

    return State(
        menu_name="PLAYER_CONTROLS",
        media_api=state.media_api,
        provider=state.provider.model_copy(
            update={
                "servers": all_servers,
                "selected_server": selected_server,
                "last_player_result": player_result,
            }
        ),
    )
