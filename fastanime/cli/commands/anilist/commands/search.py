from typing import TYPE_CHECKING

import click
from fastanime.cli.utils.completions import anime_titles_shell_complete

from .data import (
    genres_available,
    media_formats_available,
    media_statuses_available,
    seasons_available,
    sorts_available,
    tags_available_list,
    years_available,
)

if TYPE_CHECKING:
    from fastanime.core.config import AppConfig


@click.command(
    help="Search for anime using anilists api and get top ~50 results",
    short_help="Search for anime",
)
@click.option("--title", "-t", shell_complete=anime_titles_shell_complete)
@click.option(
    "--dump-json",
    "-d",
    is_flag=True,
    help="Only print out the results dont open anilist menu",
)
@click.option(
    "--season",
    help="The season the media was released",
    type=click.Choice(seasons_available),
)
@click.option(
    "--status",
    "-S",
    help="The media status of the anime",
    multiple=True,
    type=click.Choice(media_statuses_available),
)
@click.option(
    "--sort",
    "-s",
    help="What to sort the search results on",
    type=click.Choice(sorts_available),
)
@click.option(
    "--genres",
    "-g",
    multiple=True,
    help="the genres to filter by",
    type=click.Choice(genres_available),
)
@click.option(
    "--tags",
    "-T",
    multiple=True,
    help="the tags to filter by",
    type=click.Choice(tags_available_list),
)
@click.option(
    "--media-format",
    "-f",
    multiple=True,
    help="Media format",
    type=click.Choice(media_formats_available),
)
@click.option(
    "--year",
    "-y",
    type=click.Choice(years_available),
    help="the year the media was released",
)
@click.option(
    "--on-list/--not-on-list",
    "-L/-no-L",
    help="Whether the anime should be in your list or not",
    type=bool,
)
@click.pass_obj
def search(
    config: "AppConfig",
    title: str,
    dump_json: bool,
    season: str,
    status: tuple,
    sort: str,
    genres: tuple,
    tags: tuple,
    media_format: tuple,
    year: str,
    on_list: bool,
):
    import json

    from fastanime.cli.utils.feedback import create_feedback_manager
    from fastanime.core.exceptions import FastAnimeError
    from fastanime.libs.api.factory import create_api_client
    from fastanime.libs.api.params import ApiSearchParams
    from rich.progress import Progress

    feedback = create_feedback_manager(config.general.icons)

    try:
        # Create API client
        api_client = create_api_client(config.general.media_api, config)

        # Build search parameters
        search_params = ApiSearchParams(
            query=title,
            per_page=config.anilist.per_page or 50,
            sort=[sort] if sort else None,
            status_in=list(status) if status else None,
            genre_in=list(genres) if genres else None,
            tag_in=list(tags) if tags else None,
            format_in=list(media_format) if media_format else None,
            season=season,
            seasonYear=int(year) if year else None,
            on_list=on_list,
        )

        # Search for anime
        with Progress() as progress:
            progress.add_task("Searching anime...", total=None)
            search_result = api_client.search_media(search_params)

        if not search_result or not search_result.media:
            raise FastAnimeError("No anime found matching your search criteria")

        if dump_json:
            # Use Pydantic's built-in serialization
            print(json.dumps(search_result.model_dump(), indent=2))
        else:
            # Launch interactive session for browsing results
            from fastanime.cli.interactive.session import session

            feedback.info(
                f"Found {len(search_result.media)} anime matching your search. Launching interactive mode..."
            )
            session.load_menus_from_folder()
            session.run(config)

    except FastAnimeError as e:
        feedback.error("Search failed", str(e))
        raise click.Abort()
    except Exception as e:
        feedback.error("Unexpected error occurred", str(e))
        raise click.Abort()
