from typing import TYPE_CHECKING

from rich.console import Console
from rich.progress import Progress
from thefuzz import fuzz

from ....libs.providers.anime.params import SearchParams
from ....libs.providers.anime.types import SearchResult
from ..session import Context, session
from ..state import InternalDirective, ProviderState, State


@session.menu
def provider_search(ctx: Context, state: State) -> State | InternalDirective:
    feedback = ctx.services.feedback
    anilist_anime = state.media_api.anime
    if not anilist_anime:
        feedback.error("No AniList anime to search for", "Please select an anime first")
        return InternalDirective.BACK

    provider = ctx.provider
    selector = ctx.selector
    config = ctx.config
    feedback.clear_console()

    anilist_title = anilist_anime.title.english or anilist_anime.title.romaji
    if not anilist_title:
        feedback.error(
            "Selected anime has no searchable title",
            "This anime entry is missing required title information",
        )
        return InternalDirective.BACK

    provider_search_results = provider.search(
        SearchParams(
            query=anilist_title, translation_type=config.stream.translation_type
        )
    )

    if not provider_search_results or not provider_search_results.results:
        feedback.warning(
            f"Could not find '{anilist_title}' on {provider.__class__.__name__}",
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
            key=lambda p_title: fuzz.ratio(p_title.lower(), anilist_title.lower()),
        )
        feedback.info("Auto-selecting best match: {best_match_title}")
        selected_provider_anime = provider_results_map[best_match_title]
    else:
        choices = list(provider_results_map.keys())
        choices.append("Back")

        chosen_title = selector.choose(
            prompt=f"Confirm match for '{anilist_title}'", choices=choices
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
        from ....libs.providers.anime.params import AnimeParams

        full_provider_anime = provider.get(
            AnimeParams(id=selected_provider_anime.id, query=anilist_title.lower())
        )

    if not full_provider_anime:
        feedback.warning(
            f"Failed to fetch details for '{selected_provider_anime.title}'."
        )
        return InternalDirective.BACK

    return State(
        menu_name="EPISODES",
        media_api=state.media_api,
        provider=ProviderState(
            search_results=provider_search_results,
            anime=full_provider_anime,
        ),
    )
