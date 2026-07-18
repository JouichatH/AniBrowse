from .....libs.provider.anime.params import AnimeParams, SearchParams
from ...session import Context, session
from ...state import InternalDirective, State


def _episodes_from_ranges(text: str | None, available: list[str]) -> list[str]:
    """Episodes matching a human range string, in ``available``'s order.

    Understands episode NUMBERS (not indices): "1-24", "8", "3,5-7", open ends
    "20-" (20 onwards) and "-5" (up to 5). Unknown numbers are skipped; a
    non-parseable string yields [].
    """
    if not text or not text.strip():
        return []

    def _num(s: str) -> float | None:
        try:
            return float(s)
        except ValueError:
            return None

    wanted: list[tuple[float, float]] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo_s, _, hi_s = part.partition("-")
            lo = _num(lo_s.strip()) if lo_s.strip() else float("-inf")
            hi = _num(hi_s.strip()) if hi_s.strip() else float("inf")
            if lo is None or hi is None:
                return []
            wanted.append((lo, hi))
        else:
            v = _num(part)
            if v is None:
                return []
            wanted.append((v, v))

    out = []
    for ep in available:
        v = _num(ep)
        if v is not None and any(lo <= v <= hi for lo, hi in wanted):
            out.append(ep)
    return out


@session.menu
def download_episodes(ctx: Context, state: State) -> State | InternalDirective:
    """Menu to select and download episodes synchronously."""
    from viu_media.cli.utils.search import find_best_match_title
    from .....core.utils.normalizer import normalize_title

    feedback = ctx.feedback
    selector = ctx.selector
    media_item = state.media_api.media_item
    config = ctx.config
    provider = ctx.provider

    if not media_item:
        feedback.error("No media item selected for download.")
        return InternalDirective.BACK

    media_title = media_item.title.english or media_item.title.romaji
    if not media_title:
        feedback.error("Cannot download: Media item has no title.")
        return InternalDirective.BACK

    # Step 1: Find the anime on the provider to get a full episode list
    with feedback.progress(
        f"Searching for '{media_title}' on {provider.__class__.__name__}..."
    ):
        provider_search_results = provider.search(
            SearchParams(
                query=normalize_title(media_title, config.general.provider.value, True)
            )
        )

    if not provider_search_results or not provider_search_results.results:
        feedback.warning(f"Could not find '{media_title}' on provider.")
        return InternalDirective.BACK

    provider_results_map = {res.title: res for res in provider_search_results.results}
    best_match_title = find_best_match_title(
        provider_results_map, config.general.provider, media_item
    )
    selected_provider_anime_ref = provider_results_map[best_match_title]

    with feedback.progress(f"Fetching episode list for '{best_match_title}'..."):
        full_provider_anime = provider.get(
            AnimeParams(id=selected_provider_anime_ref.id, query=media_title)
        )

    if not full_provider_anime:
        feedback.warning(f"Failed to fetch details for '{best_match_title}'.")
        return InternalDirective.BACK

    available_episodes = getattr(
        full_provider_anime.episodes, config.stream.translation_type, []
    )
    if not available_episodes:
        feedback.warning("No episodes found for download.")
        return InternalDirective.BACK

    # Step 2: Let user select episodes. A 50-episode season must be one
    # action, not fifty TAB presses - so offer all/range alongside picking.
    icons = config.general.icons
    n = len(available_episodes)
    mode_all = f"{'📦 ' if icons else ''}All episodes ({n})"
    mode_range = f"{'🔢 ' if icons else ''}Range (e.g. 1-24 or 1,5,8-10)"
    mode_pick = f"{'☑️ ' if icons else ''}Pick individually (TAB to select)"
    mode = selector.choose(
        "Which episodes?", [mode_all, mode_range, mode_pick]
    )

    selected_episodes: list[str] = []
    if mode == mode_all:
        selected_episodes = list(available_episodes)
    elif mode == mode_range:
        range_str = selector.ask(
            f"Episodes to download (1-{available_episodes[-1]}; e.g. 1-24, 8, 3,5-7):"
        )
        selected_episodes = _episodes_from_ranges(range_str, available_episodes)
        if range_str and not selected_episodes:
            feedback.warning(
                f"'{range_str}' didn't match any available episode.",
                f"Available: {available_episodes[0]}-{available_episodes[-1]}",
            )
            return InternalDirective.BACK
    elif mode == mode_pick:
        selected_episodes = selector.choose_multiple(
            "Select episodes to download (TAB to select, ENTER to confirm)",
            choices=available_episodes,
        )

    if not selected_episodes:
        feedback.info("No episodes selected for download.")
        return InternalDirective.BACK

    if len(selected_episodes) > 5:
        confirm = selector.choose(
            f"Download {len(selected_episodes)} episodes now? (runs in the "
            "foreground and may take a long while)",
            ["Yes, download them", "Cancel"],
        )
        if confirm != "Yes, download them":
            return InternalDirective.BACK

    # Step 3: Download episodes synchronously using the session-scoped service
    feedback.info(
        f"Starting download of {len(selected_episodes)} episodes. This may take a while..."
    )
    ctx.download.download_episodes_sync(media_item, selected_episodes)

    feedback.success(f"Finished downloading {len(selected_episodes)} episodes.")

    # After downloading, return to the media actions menu
    return InternalDirective.BACK
