from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.progress import Progress
from thefuzz import fuzz

from ....libs.providers.anime.params import SearchParams
from ...utils.feedback import create_feedback_manager, execute_with_feedback
from ..session import Context, session
from ..state import ControlFlow, ProviderState, State

if TYPE_CHECKING:
    from ....libs.providers.anime.types import SearchResult


@session.menu
def provider_search(ctx: Context, state: State) -> State | ControlFlow:
    """
    Searches for the selected AniList anime on the configured provider.
    This state allows the user to confirm the correct provider entry before
    proceeding to list episodes.
    """
    feedback = create_feedback_manager(ctx.config.general.icons)
    anilist_anime = state.media_api.anime
    if not anilist_anime:
        feedback.error("No AniList anime to search for", "Please select an anime first")
        return ControlFlow.BACK

    provider = ctx.provider
    selector = ctx.selector
    config = ctx.config
    console = Console()
    console.clear()

    anilist_title = anilist_anime.title.english or anilist_anime.title.romaji
    if not anilist_title:
        feedback.error(
            "Selected anime has no searchable title",
            "This anime entry is missing required title information",
        )
        return ControlFlow.BACK

    # --- Perform Search on Provider ---
    def search_provider():
        return provider.search(
            SearchParams(
                query=anilist_title, translation_type=config.stream.translation_type
            )
        )

    success, provider_search_results = execute_with_feedback(
        search_provider,
        feedback,
        "search provider",
        loading_msg=f"Searching for '{anilist_title}' on {provider.__class__.__name__}",
        success_msg=f"Found results on {provider.__class__.__name__}",
    )

    if (
        not success
        or not provider_search_results
        or not provider_search_results.results
    ):
        feedback.warning(
            f"Could not find '{anilist_title}' on {provider.__class__.__name__}",
            "Try another provider from the config or go back to search again",
        )
        return ControlFlow.BACK

    # --- Map results for selection ---
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
        console.print(f"[cyan]Auto-selecting best match:[/] {best_match_title}")
        selected_provider_anime = provider_results_map[best_match_title]
    else:
        choices = list(provider_results_map.keys())
        choices.append("Back")

        chosen_title = selector.choose(
            prompt=f"Confirm match for '{anilist_title}'", choices=choices
        )

        if not chosen_title or chosen_title == "Back":
            return ControlFlow.BACK

        selected_provider_anime = provider_results_map[chosen_title]

    # --- Fetch Full Anime Details from Provider ---
    with Progress(transient=True) as progress:
        progress.add_task(
            f"[cyan]Fetching full details for '{selected_provider_anime.title}'...",
            total=None,
        )
        from ....libs.providers.anime.params import AnimeParams

        full_provider_anime = provider.get(AnimeParams(id=selected_provider_anime.id))

    if not full_provider_anime:
        console.print(
            f"[bold red]Failed to fetch details for '{selected_provider_anime.title}'.[/bold red]"
        )
        return ControlFlow.BACK

    return State(
        menu_name="EPISODES",
        media_api=state.media_api,
        provider=ProviderState(
            search_results=provider_search_results,
            anime=full_provider_anime,
        ),
    )
