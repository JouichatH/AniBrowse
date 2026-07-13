from typing import Callable, Dict, Literal, Union

from .....core.exceptions import NavigationAbort
from ...session import Context, session
from ...state import InternalDirective, MenuName, State

MenuAction = Callable[[], Union[State, InternalDirective]]


@session.menu
def player_controls(ctx: Context, state: State) -> Union[State, InternalDirective]:
    feedback = ctx.feedback
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
    # The current episode may not be in the provider's own list (e.g. an episode
    # merged in from nyaa), so resolve the index defensively instead of .index().
    current_index = (
        available_episodes.index(current_episode_num)
        if current_episode_num in available_episodes
        else None
    )

    # Auto-advance ONLY when the video actually reached its end — not on a manual
    # quit partway through, and not when a stream failed instantly (which previously
    # caused a rapid next/prev retry loop). "Reached the end" is stricter than the
    # watch-history completion threshold: post-ending scenes must have played out.
    if (
        config.stream.auto_next
        and state.provider.reached_end_
        and current_index is not None
        and current_index < len(available_episodes) - 1
    ):
        feedback.info("Auto-playing next episode...")
        next_episode_num = available_episodes[current_index + 1]

        return State(
            menu_name=MenuName.SERVERS,
            media_api=state.media_api,
            provider=state.provider.model_copy(update={"episode_": next_episode_num}),
        )

    # In-place loop: toggles and change-server/quality flip config and re-show
    # this same menu (they return RELOAD). Keeping the loop here - instead of
    # returning RELOAD to the session loop - lets us preserve the fzf cursor
    # position via start_index, so the user can flip several options in a row
    # without the cursor jumping back to "Next Episode" each time.
    cursor_index: Union[int, None] = None
    while True:
        # Recompute each render: a translation-type toggle switches sub<->dub and
        # changes which episodes (and hence Next/Previous) are available.
        available_episodes = getattr(
            provider_anime.episodes, config.stream.translation_type, []
        )
        options = _build_options(ctx, state, current_episode_num, available_episodes)
        choices = list(options.keys())

        try:
            choice = selector.choose(
                prompt="What's next?", choices=choices, start_index=cursor_index
            )
        except NavigationAbort:
            # Esc here: a plain BACK would pop to the servers menu, which is a
            # pass-through that silently replays the episode. Instead behave like
            # the "Episode List" action - skip the servers menu and surface the
            # episode list so Esc backs out instead of restarting playback.
            ctx.switch.force_episodes_menu()
            return InternalDirective.BACKX2

        if not choice or choice not in options:
            # No selection (e.g. Enter on an unmatched query): re-show in place.
            cursor_index = None
            continue

        result = options[choice]()
        if result == InternalDirective.RELOAD:
            # An in-place action (toggle / change server / change quality): keep
            # the cursor on the row the user just acted on and re-render.
            cursor_index = choices.index(choice)
            continue
        return result


def _build_options(
    ctx: Context,
    state: State,
    current_episode_num: str,
    available_episodes: list,
) -> Dict[str, "MenuAction"]:
    """Build the "What's next?" options for the current episode/config.

    Rebuilt on every render so the Toggle labels reflect the live config values
    and Next/Previous availability tracks the (possibly re-resolved) episode list.
    """
    config = ctx.config
    icons = config.general.icons
    current_index = (
        available_episodes.index(current_episode_num)
        if current_episode_num in available_episodes
        else None
    )

    options: Dict[str, Callable[[], Union[State, InternalDirective]]] = {}

    if current_index is not None and current_index < len(available_episodes) - 1:
        options[f"{'⏭️ ' if icons else ''}Next Episode"] = _next_episode(ctx, state)
    if current_index:
        options[f"{'⏪ ' if icons else ''}Previous Episode"] = _previous_episode(
            ctx, state
        )

    options.update(
        {
            f"{'🔂 ' if icons else ''}Replay": _replay(ctx, state),
            f"{'💽 ' if icons else ''}Change Server": _change_server(ctx, state),
            f"{'📀 ' if icons else ''}Change Quality": _change_quality(ctx, state),
            f"{'🎞️ ' if icons else ''}Episode List": _episodes_list(ctx, state),
            f"{'🔘 ' if icons else ''}Toggle Auto Next Episode (Current: {config.stream.auto_next})": _toggle_config_state(
                ctx, state, "AUTO_EPISODE"
            ),
            f"{'⏩ ' if icons else ''}Toggle Opening Skip (Current: {config.stream.opening_skip})": _toggle_config_state(
                ctx, state, "OPENING_SKIP"
            ),
            f"{'⏩ ' if icons else ''}Toggle Ending Skip (Current: {config.stream.ending_skip})": _toggle_config_state(
                ctx, state, "ENDING_SKIP"
            ),
            f"{'🔘 ' if icons else ''}Toggle Translation Type  (Current: {config.stream.translation_type.upper()})": _toggle_config_state(
                ctx, state, "TRANSLATION_TYPE"
            ),
            f"{'🎥 ' if icons else ''}Media Actions Menu": lambda: InternalDirective.BACKX4,
            f"{'🏠 ' if icons else ''}Main Menu": lambda: InternalDirective.MAIN,
            f"{'❌ ' if icons else ''}Exit": lambda: InternalDirective.EXIT,
        }
    )
    return options


def _next_episode(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = ctx.feedback

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
        if current_episode_num not in available_episodes:
            feedback.warning(
                "Current episode isn't in this provider's list; can't navigate."
            )
            return InternalDirective.RELOAD
        current_index = available_episodes.index(current_episode_num)

        if current_index < len(available_episodes) - 1:
            next_episode_num = available_episodes[current_index + 1]

            return State(
                menu_name=MenuName.SERVERS,
                media_api=state.media_api,
                provider=state.provider.model_copy(
                    update={"episode_": next_episode_num}
                ),
            )
        feedback.warning("This is the last available episode.")
        return InternalDirective.RELOAD

    return action


def _previous_episode(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = ctx.feedback

        config = ctx.config

        provider_anime = state.provider.anime
        current_episode_num = state.provider.episode

        if not provider_anime or not current_episode_num:
            feedback.error("Player state is incomplete. Returning.")
            return InternalDirective.BACK

        available_episodes = getattr(
            provider_anime.episodes, config.stream.translation_type, []
        )
        if current_episode_num not in available_episodes:
            feedback.warning(
                "Current episode isn't in this provider's list; can't navigate."
            )
            return InternalDirective.RELOAD
        current_index = available_episodes.index(current_episode_num)

        if current_index:
            prev_episode_num = available_episodes[current_index - 1]

            return State(
                menu_name=MenuName.SERVERS,
                media_api=state.media_api,
                provider=state.provider.model_copy(
                    update={"episode_": prev_episode_num}
                ),
            )
        feedback.warning("This is the last available episode.")
        return InternalDirective.RELOAD

    return action


def _replay(ctx: Context, state: State) -> MenuAction:
    def action():
        return InternalDirective.BACK

    return action


def _toggle_config_state(
    ctx: Context,
    state: State,
    config_state: Literal[
        "AUTO_ANIME",
        "AUTO_EPISODE",
        "OPENING_SKIP",
        "ENDING_SKIP",
        "CONTINUE_FROM_HISTORY",
        "TRANSLATION_TYPE",
    ],
) -> MenuAction:
    def action():
        match config_state:
            case "AUTO_ANIME":
                ctx.config.general.auto_select_anime_result = (
                    not ctx.config.general.auto_select_anime_result
                )
            case "AUTO_EPISODE":
                ctx.config.stream.auto_next = not ctx.config.stream.auto_next
            case "OPENING_SKIP":
                ctx.config.stream.opening_skip = not ctx.config.stream.opening_skip
            case "ENDING_SKIP":
                ctx.config.stream.ending_skip = not ctx.config.stream.ending_skip
            case "CONTINUE_FROM_HISTORY":
                ctx.config.stream.continue_from_watch_history = (
                    not ctx.config.stream.continue_from_watch_history
                )
            case "TRANSLATION_TYPE":
                ctx.config.stream.translation_type = (
                    "sub" if ctx.config.stream.translation_type == "dub" else "dub"
                )
        return InternalDirective.RELOAD

    return action


def _change_server(ctx: Context, state: State) -> MenuAction:
    def action():
        from .....libs.provider.anime.types import ProviderServer

        feedback = ctx.feedback

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
            ctx.config.stream.server = ProviderServer(new_server_name)
        return InternalDirective.RELOAD

    return action


def _episodes_list(ctx: Context, state: State) -> MenuAction:
    def action():
        ctx.switch.force_episodes_menu()
        return InternalDirective.BACKX2

    return action


def _change_quality(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = ctx.feedback

        selector = ctx.selector

        server_map = state.provider.servers

        if not server_map:
            feedback.error("Player state is incomplete. Returning.")
            return InternalDirective.BACK

        new_quality = selector.choose(
            "Select a different quality:",
            [link.quality for link in state.provider.server.links],
        )
        if new_quality:
            ctx.config.stream.quality = new_quality  # type:ignore
        return InternalDirective.RELOAD

    return action
