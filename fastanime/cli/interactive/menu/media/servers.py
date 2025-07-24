from typing import Dict, List

from .....libs.player.params import PlayerParams
from .....libs.provider.anime.params import EpisodeStreamsParams
from .....libs.provider.anime.types import ProviderServer, Server
from ...session import Context, session
from ...state import InternalDirective, MenuName, State


@session.menu
def servers(ctx: Context, state: State) -> State | InternalDirective:
    feedback = ctx.services.feedback

    config = ctx.config
    provider = ctx.provider
    selector = ctx.selector

    provider_anime = state.provider.anime
    media_item = state.media_api.media_item

    if not media_item:
        return InternalDirective.BACK
    anime_title = media_item.title.romaji or media_item.title.english
    episode_number = state.provider.episode

    if not provider_anime or not episode_number:
        feedback.error("Anime or episode details are missing")
        return InternalDirective.BACK

    with feedback.progress("Fetching Servers"):
        server_iterator = provider.episode_streams(
            EpisodeStreamsParams(
                anime_id=provider_anime.id,
                query=anime_title,
                episode=episode_number,
                translation_type=config.stream.translation_type,
            )
        )
        # Consume the iterator to get a list of all servers
        if config.stream.server == ProviderServer.TOP and server_iterator:
            try:
                all_servers = [next(server_iterator)]
            except Exception:
                all_servers = []
        else:
            all_servers: List[Server] = list(server_iterator) if server_iterator else []

    if not all_servers:
        feedback.error("o streaming servers found for this episode")
        return InternalDirective.BACK

    server_map: Dict[str, Server] = {s.name: s for s in all_servers}
    selected_server: Server | None = None

    preferred_server = config.stream.server.value.lower()
    if preferred_server == "top":
        selected_server = all_servers[0]
        feedback.info(f"Auto-selecting top server: {selected_server.name}")
    elif preferred_server in server_map:
        selected_server = server_map[preferred_server]
        feedback.info(f"Auto-selecting preferred server: {selected_server.name}")
    else:
        choices = [*server_map.keys(), "Back"]
        chosen_name = selector.choose("Select Server", choices)
        if not chosen_name or chosen_name == "Back":
            return InternalDirective.BACK
        selected_server = server_map[chosen_name]

    stream_link_obj = _filter_by_quality(selected_server.links, config.stream.quality)
    if not stream_link_obj:
        feedback.error(
            f"No stream of quality '{config.stream.quality}' found on server '{selected_server.name}'."
        )
        return InternalDirective.RELOAD

    final_title = f"{provider_anime.title} - Ep {episode_number}"
    feedback.info(f"[bold green]Launching player for:[/] {final_title}")

    player_result = ctx.player.play(
        PlayerParams(
            url=stream_link_obj.link,
            title=final_title,
            subtitles=[sub.url for sub in selected_server.subtitles],
            headers=selected_server.headers,
        )
    )
    if media_item and episode_number:
        ctx.services.watch_history.track(media_item, episode_number, player_result)

    return State(
        menu_name=MenuName.PLAYER_CONTROLS,
        media_api=state.media_api,
        provider=state.provider.model_copy(
            update={
                "servers": server_map,
                "server_name": selected_server.name,
            }
        ),
    )


def _filter_by_quality(links, quality):
    # Simplified version of your filter_by_quality for brevity
    for link in links:
        if str(link.quality) == quality:
            return link
    return links[0] if links else None
