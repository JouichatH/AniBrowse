from rich.progress import Progress
from .....core.utils.fuzzy import fuzz

from .....libs.provider.anime.params import SearchParams
from .....libs.provider.anime.types import SearchResult
from ...session import Context, session
from ...state import InternalDirective, MenuName, ProviderState, State


@session.menu
def provider_search(ctx: Context, state: State) -> State | InternalDirective:
    feedback = ctx.service.feedback
    media_item = state.media_api.media_item
    if not media_item:
        feedback.error("No AniList anime to search for", "Please select an anime first")
        return InternalDirective.BACK

    provider = ctx.provider
    selector = ctx.selector
    config = ctx.config
    feedback.clear_console()

    media_title = media_item.title.english or media_item.title.romaji
    if not media_title:
        feedback.error(
            "Selected anime has no searchable title",
            "This anime entry is missing required title information",
        )
        return InternalDirective.BACK

    provider_search_results = provider.search(
        SearchParams(query=media_title, translation_type=config.stream.translation_type)
    )

    if not provider_search_results or not provider_search_results.results:
        feedback.warning(
            f"Could not find '{media_title}' on {provider.__class__.__name__}",
            "Try another provider from the config or go back to search again",
        )
        return InternalDirective.BACK

    provider_results_map: dict[str, SearchResult] = {
        result.title: result for result in provider_search_results.results
    }

    selected_provider_anime: SearchResult | None = None

    # --- Auto-Select or Prompt ---
    if config.general.auto_select_anime_result:
        # Use fuzzy matching to find the best title
        best_match_title = max(
            provider_results_map.keys(),
            key=lambda p_title: fuzz.ratio(p_title.lower(), media_title.lower()),
        )
        feedback.info("Auto-selecting best match: {best_match_title}")
        selected_provider_anime = provider_results_map[best_match_title]
    else:
        choices = list(provider_results_map.keys())
        choices.append("Back")

        chosen_title = selector.choose(
            prompt=f"Confirm match for '{media_title}'", choices=choices
        )

        if not chosen_title or chosen_title == "Back":
            return InternalDirective.BACK

        selected_provider_anime = provider_results_map[chosen_title]

    # --- Fetch Full Anime Details from Provider ---
    with Progress(transient=True) as progress:
        progress.add_task(
            f"[cyan]Fetching full details for '{selected_provider_anime.title}'...",
            total=None,
        )
        from .....libs.provider.anime.params import AnimeParams

        full_provider_anime = provider.get(
            AnimeParams(id=selected_provider_anime.id, query=media_title.lower())
        )

    if not full_provider_anime:
        feedback.warning(
            f"Failed to fetch details for '{selected_provider_anime.title}'."
        )
        return InternalDirective.BACK

    return State(
        menu_name=MenuName.EPISODES,
        media_api=state.media_api,
        provider=ProviderState(
            search_results=provider_search_results,
            anime=full_provider_anime,
        ),
    )
