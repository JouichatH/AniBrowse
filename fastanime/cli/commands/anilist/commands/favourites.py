from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from fastanime.core.config import AppConfig


@click.command(
    help="Fetch the top 15 most favourited anime from anilist",
    short_help="View most favourited anime",
)
@click.option(
    "--dump-json",
    "-d",
    is_flag=True,
    help="Only print out the results dont open anilist menu",
)
@click.pass_obj
def favourites(config: "AppConfig", dump_json: bool):
    from fastanime.libs.api.params import MediaSearchParams
    from ..helpers import handle_media_search_command

    def create_search_params(config):
        return MediaSearchParams(
            per_page=config.anilist.per_page or 15,
            sort=["FAVOURITES_DESC"]
        )

    handle_media_search_command(
        config=config,
        dump_json=dump_json,
        task_name="Fetching most favourited anime...",
        search_params_factory=create_search_params,
        empty_message="No favourited anime found"
    )

        exit(1)
