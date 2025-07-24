"""
Registry search command - search through the local media registry
"""

import click
from rich.console import Console
from rich.table import Table

from .....core.config import AppConfig
from .....libs.media_api.params import MediaSearchParams
from .....libs.media_api.types import MediaSort, UserMediaListStatus
from ....service.registry.service import MediaRegistryService
from ....utils.feedback import create_feedback_manager


@click.command(help="Search through the local media registry")
@click.argument("query", required=False)
@click.option(
    "--status",
    type=click.Choice([
        "watching", "completed", "planning", "dropped", "paused", "repeating"
    ], case_sensitive=False),
    help="Filter by watch status"
)
@click.option(
    "--genre",
    multiple=True,
    help="Filter by genre (can be used multiple times)"
)
@click.option(
    "--format",
    type=click.Choice([
        "TV", "TV_SHORT", "MOVIE", "SPECIAL", "OVA", "ONA", "MUSIC"
    ], case_sensitive=False),
    help="Filter by format"
)
@click.option(
    "--year",
    type=int,
    help="Filter by release year"
)
@click.option(
    "--min-score",
    type=float,
    help="Minimum average score (0.0 - 10.0)"
)
@click.option(
    "--max-score", 
    type=float,
    help="Maximum average score (0.0 - 10.0)"
)
@click.option(
    "--sort",
    type=click.Choice([
        "title", "score", "popularity", "year", "episodes", "updated"
    ], case_sensitive=False),
    default="title",
    help="Sort results by field"
)
@click.option(
    "--limit",
    type=int,
    default=20,
    help="Maximum number of results to show"
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results in JSON format"
)
@click.option(
    "--api",
    default="anilist",
    type=click.Choice(["anilist"], case_sensitive=False),
    help="Media API registry to search"
)
@click.pass_obj
def search(
    config: AppConfig,
    query: str | None,
    status: str | None,
    genre: tuple[str, ...],
    format: str | None,
    year: int | None,
    min_score: float | None,
    max_score: float | None,
    sort: str,
    limit: int,
    output_json: bool,
    api: str
):
    """
    Search through your local media registry.
    
    You can search by title and filter by various criteria like status,
    genre, format, year, and score range.
    """
    feedback = create_feedback_manager(config.general.icons)
    console = Console()
    
    try:
        registry_service = MediaRegistryService(api, config.registry)
        
        # Build search parameters
        search_params = _build_search_params(
            query, status, genre, format, year, min_score, max_score, sort, limit
        )
        
        # Perform search
        result = registry_service.search_for_media(search_params)
        
        if not result or not result.media:
            feedback.info("No Results", "No media found matching your criteria")
            return
        
        if output_json:
            import json
            print(json.dumps(result.model_dump(), indent=2, default=str))
            return
        
        _display_search_results(console, result, config.general.icons)
        
    except Exception as e:
        feedback.error("Search Error", f"Failed to search registry: {e}")
        raise click.Abort()


def _build_search_params(
    query, status, genre, format, year, min_score, max_score, sort, limit
) -> MediaSearchParams:
    """Build MediaSearchParams from command options."""
    
    # Convert status string to enum
    status_enum = None
    if status:
        status_map = {
            "watching": UserMediaListStatus.WATCHING,
            "completed": UserMediaListStatus.COMPLETED, 
            "planning": UserMediaListStatus.PLANNING,
            "dropped": UserMediaListStatus.DROPPED,
            "paused": UserMediaListStatus.PAUSED,
            "repeating": UserMediaListStatus.REPEATING,
        }
        status_enum = status_map.get(status.lower())
    
    # Convert sort string to enum
    sort_map = {
        "title": MediaSort.TITLE_ROMAJI,
        "score": MediaSort.SCORE_DESC,
        "popularity": MediaSort.POPULARITY_DESC,
        "year": MediaSort.START_DATE_DESC,
        "episodes": MediaSort.EPISODES_DESC,
        "updated": MediaSort.UPDATED_AT_DESC,
    }
    sort_enum = sort_map.get(sort.lower(), MediaSort.TITLE_ROMAJI)
    
    # Convert format string to enum if provided
    format_enum = None
    if format:
        from .....libs.media_api.types import MediaFormat
        format_enum = getattr(MediaFormat, format.upper(), None)
    
    # Convert genre strings to enums
    genre_enums = []
    if genre:
        from .....libs.media_api.types import MediaGenre
        for g in genre:
            # Try to find matching genre enum
            for genre_enum in MediaGenre:
                if genre_enum.value.lower() == g.lower():
                    genre_enums.append(genre_enum)
                    break
    
    return MediaSearchParams(
        query=query,
        per_page=limit,
        sort=[sort_enum],
        averageScore_greater=min_score * 10 if min_score else None,  # Convert to AniList scale
        averageScore_lesser=max_score * 10 if max_score else None,
        genre_in=genre_enums if genre_enums else None,
        format_in=[format_enum] if format_enum else None,
        seasonYear=year,
        # We'll handle status filtering differently since it's user-specific
    )


def _display_search_results(console: Console, result, icons: bool):
    """Display search results in a formatted table."""
    
    table = Table(title=f"{'🔍 ' if icons else ''}Search Results ({len(result.media)} found)")
    table.add_column("Title", style="cyan", min_width=30)
    table.add_column("Year", style="dim", justify="center", min_width=6)
    table.add_column("Format", style="magenta", justify="center", min_width=8)
    table.add_column("Episodes", style="green", justify="center", min_width=8)
    table.add_column("Score", style="yellow", justify="center", min_width=6)
    table.add_column("Status", style="blue", justify="center", min_width=10)
    table.add_column("Progress", style="white", justify="center", min_width=8)
    
    for media in result.media:
        # Get title (prefer English, fallback to Romaji)
        title = media.title.english or media.title.romaji or "Unknown"
        if len(title) > 40:
            title = title[:37] + "..."
        
        # Get year from start date
        year = ""
        if media.start_date:
            year = str(media.start_date.year)
        
        # Format episodes
        episodes = str(media.episodes) if media.episodes else "?"
        
        # Format score
        score = f"{media.average_score/10:.1f}" if media.average_score else "N/A"
        
        # Get user status
        status = "Not Listed"
        progress = "0"
        if media.user_status:
            status = media.user_status.status.value.title() if media.user_status.status else "Unknown"
            progress = f"{media.user_status.progress or 0}/{episodes}"
        
        table.add_row(
            title,
            year,
            media.format.value if media.format else "Unknown",
            episodes,
            score,
            status,
            progress
        )
    
    console.print(table)
    
    # Show pagination info if applicable
    if result.page_info.total > len(result.media):
        console.print(
            f"\n[dim]Showing {len(result.media)} of {result.page_info.total} total results[/dim]"
        )
