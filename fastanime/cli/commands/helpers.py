import click

from ...core.config import AppConfig
from ...libs.api.factory import create_api_client
from ...libs.api.params import ApiSearchParams


@click.group(hidden=True)
def helpers_cmd():
    """A hidden group for helper commands called by shell scripts."""
    pass


@helpers_cmd.command("search-as-you-type")
@click.argument("query", required=False, default="")
@click.pass_obj
def search_as_you_type(config: AppConfig, query: str):
    """
    Performs a live search on AniList and prints results formatted for fzf.
    Called by an fzf `reload` binding.
    """
    if not query or len(query) < 3:
        # Don't search for very short queries to avoid spamming the API
        return

    api_client = create_api_client(config.general.api_client, config)
    search_params = ApiSearchParams(query=query, per_page=25)
    results = api_client.search_media(search_params)

    if not results or not results.media:
        return

    # Format output for fzf: one line per item.
    for item in results.media:
        title = item.title.english or item.title.romaji or "Unknown Title"
        score = f"{item.average_score / 10 if item.average_score else 'N/A'}"
        # Use a unique, parsable format. The title must come last for the preview helper.
        click.echo(f"{item.id} | Score: {score} | {title}")
