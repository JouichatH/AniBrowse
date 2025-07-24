from typing import Callable, Dict, Union

from ...session import Context, session
from ...state import InternalDirective, MenuName, State

MenuAction = Callable[[], Union[State, InternalDirective]]


@session.menu
def player_controls(ctx: Context, state: State) -> Union[State, InternalDirective]:
    feedback = ctx.services.feedback
    feedback.clear_console()

    config = ctx.config
    selector = ctx.selector

    provider_anime = state.provider.anime
    media_item = state.media_api.media_item
    current_episode_num = state.provider.episode
    selected_server = state.provider.server
    server_map = state.provider.servers

    if (
        not provider_anime
        or not media_item
        or not current_episode_num
        or not selected_server
        or not server_map
    ):
        feedback.error("Player state is incomplete. Returning.")
        return InternalDirective.BACK

    available_episodes = getattr(
        provider_anime.episodes, config.stream.translation_type, []
    )
    current_index = available_episodes.index(current_episode_num)

    if config.stream.auto_next and current_index < len(available_episodes) - 1:
        feedback.info("Auto-playing next episode...")
        next_episode_num = available_episodes[current_index + 1]

        return State(
            menu_name=MenuName.SERVERS,
            media_api=state.media_api,
            provider=state.provider.model_copy(
                update={"episode_number": next_episode_num}
            ),
        )

    # --- Menu Options ---
    icons = config.general.icons
    options: Dict[str, Callable[[], Union[State, InternalDirective]]] = {}

    if current_index < len(available_episodes) - 1:
        options[f"{'⏭️ ' if icons else ''}Next Episode"] = _next_episode(ctx, state)

    options.update(
        {
            f"{'🔄 ' if icons else ''}Replay Episode": _replay(ctx, state),
            f"{'💻 ' if icons else ''}Change Server": _change_server(ctx, state),
            f"{'🎞️ ' if icons else ''}Back to Episode List": lambda: State(
                menu_name=MenuName.EPISODES,
                media_api=state.media_api,
                provider=state.provider,
            ),
            f"{'🏠 ' if icons else ''}Main Menu": lambda: State(
                menu_name=MenuName.MAIN
            ),
            f"{'❌ ' if icons else ''}Exit": lambda: InternalDirective.EXIT,
        }
    )

    choice = selector.choose(prompt="What's next?", choices=list(options.keys()))

    if choice and choice in options:
        return options[choice]()

    return InternalDirective.BACK


def _next_episode(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = ctx.services.feedback
        feedback.clear_console()

        config = ctx.config

        provider_anime = state.provider.anime
        media_item = state.media_api.media_item
        current_episode_num = state.provider.episode
        selected_server = state.provider.server
        server_map = state.provider.servers

        if (
            not provider_anime
            or not media_item
            or not current_episode_num
            or not selected_server
            or not server_map
        ):
            feedback.error("Player state is incomplete. Returning.")
            return InternalDirective.BACK

        available_episodes = getattr(
            provider_anime.episodes, config.stream.translation_type, []
        )
        current_index = available_episodes.index(current_episode_num)

        if current_index < len(available_episodes) - 1:
            next_episode_num = available_episodes[current_index + 1]

            return State(
                menu_name=MenuName.SERVERS,
                media_api=state.media_api,
                provider=state.provider.model_copy(
                    update={"episode_number": next_episode_num}
                ),
            )
        feedback.warning("This is the last available episode.")
        return InternalDirective.RELOAD

    return action


def _replay(ctx: Context, state: State) -> MenuAction:
    def action():
        return InternalDirective.BACK

    return action


def _change_server(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = ctx.services.feedback
        feedback.clear_console()

        selector = ctx.selector

        provider_anime = state.provider.anime
        media_item = state.media_api.media_item
        current_episode_num = state.provider.episode
        selected_server = state.provider.server
        server_map = state.provider.servers

        if (
            not provider_anime
            or not media_item
            or not current_episode_num
            or not selected_server
            or not server_map
        ):
            feedback.error("Player state is incomplete. Returning.")
            return InternalDirective.BACK

        new_server_name = selector.choose(
            "Select a different server:", list(server_map.keys())
        )
        if new_server_name:
            return State(
                menu_name=MenuName.SERVERS,
                media_api=state.media_api,
                provider=state.provider.model_copy(
                    update={"selected_server": server_map[new_server_name]}
                ),
            )
        return InternalDirective.RELOAD

    return action
