from .....core.exceptions import NavigationAbort
from ...session import Context, session
from ...state import InternalDirective, MenuName, State


@session.menu
def episodes(ctx: Context, state: State) -> State | InternalDirective:
    """
    Displays available episodes for a selected provider anime and handles
    the logic for continuing from watch history or manual selection.
    """
    config = ctx.config
    feedback = ctx.feedback
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

    # If the active source lags behind the broadcast (a simulcast episode has
    # aired but this provider hasn't uploaded it yet), merge in the missing
    # episodes from nyaa torrents so they stay selectable. Streaming those is
    # handled by the nyaa fallback in the servers menu.
    if getattr(config.stream, "nyaa_fallback", True) and type(
        ctx.provider
    ).__name__ != "Nyaa":
        last_aired = None
        next_airing = media_item.next_airing
        if next_airing:
            last_aired = next_airing.episode - 1
        elif media_item.episodes:
            last_aired = media_item.episodes
        if last_aired:
            max_available = max(
                (float(e) for e in available_episodes if e.replace(".", "", 1).isdigit()),
                default=0.0,
            )
            if last_aired > max_available:
                from ._source_fallback import merge_episodes, nyaa_extra_episodes

                anime_title = media_item.title.romaji or media_item.title.english
                with feedback.progress("Source is behind — checking nyaa for newer episodes"):
                    extras = nyaa_extra_episodes(
                        anime_title, list(available_episodes), int(last_aired)
                    )
                if extras:
                    available_episodes = merge_episodes(list(available_episodes), extras)
                    feedback.info(
                        f"Added {len(extras)} newer episode(s) from nyaa: "
                        f"{', '.join(extras)}"
                    )

    chosen_episode: str | None = None
    start_time: str | None = None

    if config.stream.continue_from_watch_history:
        chosen_episode, start_time = ctx.watch_history.get_episode(media_item)

    if not chosen_episode or ctx.switch.show_episodes_menu:
        choices = [*available_episodes, "Back"]

        # Esc (NavigationAbort) must back out the same way the explicit "Back"
        # choice does: this menu's parent is the pass-through provider-search
        # menu, so a single BACK would just re-run that search and land right
        # back here. BACKX2 skips it and returns to the media-actions menu.
        try:
            preview_command = None
            if ctx.config.general.preview != "none":
                from ....utils.preview import create_preview_context

                with create_preview_context() as preview_ctx:
                    preview_command = preview_ctx.get_episode_preview(
                        available_episodes, media_item, ctx.config
                    )

                    chosen_episode_str = ctx.selector.choose(
                        prompt="Select Episode",
                        choices=choices,
                        preview=preview_command,
                    )
                    # Workers are automatically cleaned up when exiting the context
            else:
                # No preview mode
                chosen_episode_str = ctx.selector.choose(
                    prompt="Select Episode", choices=choices, preview=None
                )
        except NavigationAbort:
            return InternalDirective.BACKX2

        if not chosen_episode_str or chosen_episode_str == "Back":
            return InternalDirective.BACKX2

        chosen_episode = chosen_episode_str

    return State(
        menu_name=MenuName.SERVERS,
        media_api=state.media_api,
        provider=state.provider.model_copy(
            update={"episode_": chosen_episode, "start_time_": start_time}
        ),
    )
