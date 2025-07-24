from ...session import Context, session
from ...state import InternalDirective, MenuName, State


@session.menu
def episodes(ctx: Context, state: State) -> State | InternalDirective:
    """
    Displays available episodes for a selected provider anime and handles
    the logic for continuing from watch history or manual selection.
    """
    config = ctx.config
    feedback = ctx.service.feedback
    feedback.clear_console()

    provider_anime = state.provider.anime
    media_item = state.media_api.media_item

    if not provider_anime or not media_item:
        feedback.error("Error: Anime details are missing.")
        return InternalDirective.BACK

    available_episodes = getattr(
        provider_anime.episodes, config.stream.translation_type, []
    )
    if not available_episodes:
        feedback.warning(
            f"No '{config.stream.translation_type}' episodes found for this anime."
        )
        return InternalDirective.BACKX2

    chosen_episode: str | None = None

    if config.stream.continue_from_watch_history:
        # TODO: implement watch history logic
        pass

    if not chosen_episode:
        choices = [*sorted(available_episodes, key=float), "Back"]

        preview_command = None
        if ctx.config.general.preview != "none":
            from ....utils.preview import get_episode_preview

            preview_command = get_episode_preview(
                available_episodes, media_item, ctx.config
            )

        chosen_episode_str = ctx.selector.choose(
            prompt="Select Episode", choices=choices, preview=preview_command
        )

        if not chosen_episode_str or chosen_episode_str == "Back":
            # TODO: should improve the back logic for menus that can be pass through
            return InternalDirective.BACKX2

        chosen_episode = chosen_episode_str

    # Track episode selection in watch history (if enabled in config)
    if (
        config.stream.continue_from_watch_history
        and config.stream.preferred_watch_history == "local"
    ):
        # TODO: implement watch history logic
        pass

    return State(
        menu_name=MenuName.SERVERS,
        media_api=state.media_api,
        provider=state.provider.model_copy(update={"episode": chosen_episode}),
    )
