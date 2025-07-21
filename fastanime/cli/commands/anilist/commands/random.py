from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from fastanime.core.config import AppConfig


@click.command(
    help="Get random anime from anilist based on a range of anilist anime ids that are selected at random",
    short_help="View random anime",
)
@click.option(
    "--dump-json",
    "-d",
    is_flag=True,
    help="Only print out the results dont open anilist menu",
)
@click.pass_obj
def random_anime(config: "AppConfig", dump_json: bool):
    import json
    import random

    from fastanime.cli.utils.feedback import create_feedback_manager
    from fastanime.core.exceptions import FastAnimeError
    from fastanime.libs.api.factory import create_api_client
    from fastanime.libs.api.params import ApiSearchParams
    from rich.progress import Progress

    feedback = create_feedback_manager(config.general.icons)

    try:
        # Create API client
        api_client = create_api_client(config.general.media_api, config)

        # Generate random IDs
        random_ids = random.sample(range(1, 100000), k=50)

        # Search for random anime
        with Progress() as progress:
            progress.add_task("Fetching random anime...", total=None)
            search_params = ApiSearchParams(id_in=random_ids, per_page=50)
            search_result = api_client.search_media(search_params)

        if not search_result or not search_result.media:
            raise FastAnimeError("No random anime found")

        if dump_json:
            # Use Pydantic's built-in serialization
            print(json.dumps(search_result.model_dump(), indent=2))
        else:
            # Launch interactive session for browsing results
            from fastanime.cli.interactive.session import session

            feedback.info(
                f"Found {len(search_result.media)} random anime. Launching interactive mode..."
            )
            session.load_menus_from_folder()
            session.run(config)

    except FastAnimeError as e:
        feedback.error("Failed to fetch random anime", str(e))
        raise click.Abort()
    except Exception as e:
        feedback.error("Unexpected error occurred", str(e))
        raise click.Abort()
