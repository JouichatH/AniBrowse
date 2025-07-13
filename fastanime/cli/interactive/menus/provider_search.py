from typing import TYPE_CHECKING

import click
from rich.progress import Progress
from thefuzz import fuzz

from ....libs.providers.anime.params import SearchParams
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
    anilist_anime = state.media_api.anime
    if not anilist_anime:
        click.echo("[bold red]Error: No AniList anime to search for.[/bold red]")
        return ControlFlow.BACK

    provider = ctx.provider
    selector = ctx.selector
    config = ctx.config

    anilist_title = anilist_anime.title.english or anilist_anime.title.romaji
    if not anilist_title:
        click.echo(
            "[bold red]Error: Selected anime has no searchable title.[/bold red]"
        )
        return ControlFlow.BACK

    # --- Perform Search on Provider ---
    with Progress(transient=True) as progress:
        progress.add_task(
            f"[cyan]Searching for '{anilist_title}' on {provider.__class__.__name__}...",
            total=None,
        )
        provider_search_results = provider.search(
            SearchParams(
                query=anilist_title, translation_type=config.stream.translation_type
            )
        )

    if not provider_search_results or not provider_search_results.results:
        click.echo(
            f"[bold yellow]Could not find '{anilist_title}' on {provider.__class__.__name__}.[/bold yellow]"
        )
        click.echo("Try another provider from the config or go back.")
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
        click.echo(f"[cyan]Auto-selecting best match:[/] {best_match_title}")
        selected_provider_anime = provider_results_map[best_match_title]
    else:
        choices = list(provider_results_map.keys())
        choices.append("Back")

        chosen_title = selector.choose(
            prompt=f"Confirm match for '{anilist_title}'",
            choices=choices,
            header="Provider Search Results",
        )

        if not chosen_title or chosen_title == "Back":
            return ControlFlow.BACK

        selected_provider_anime = provider_results_map[chosen_title]

    if not selected_provider_anime:
        return ControlFlow.BACK

    # --- Fetch Full Anime Details from Provider ---
    with Progress(transient=True) as progress:
        progress.add_task(
            f"[cyan]Fetching full details for '{selected_provider_anime.title}'...",
            total=None,
        )
        from ....libs.providers.anime.params import AnimeParams

        full_provider_anime = provider.get(AnimeParams(id=selected_provider_anime.id))

    if not full_provider_anime:
        click.echo(
            f"[bold red]Failed to fetch details for '{selected_provider_anime.title}'.[/bold red]"
        )
        return ControlFlow.BACK

    # --- Transition to Episodes Menu ---
    # Create the next state, populating the 'provider' field for the first time
    # while carrying over the 'media_api' state.
    return State(
        menu_name="EPISODES",
        media_api=state.media_api,
        provider=ProviderState(
            search_results=provider_search_results,
            anime=full_provider_anime,
        ),
    )
