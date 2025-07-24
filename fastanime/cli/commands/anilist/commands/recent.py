from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from fastanime.core.config import AppConfig


@click.command(
    help="Fetch the 15 most recently updated anime from anilist that are currently releasing",
    short_help="View recently updated anime",
)
@click.option(
    "--dump-json",
    "-d",
    is_flag=True,
    help="Only print out the results dont open anilist menu",
)
@click.pass_obj
def recent(config: "AppConfig", dump_json: bool):
    from fastanime.libs.api.params import MediaSearchParams
    from ..helpers import handle_media_search_command

    def create_search_params(config):
        return MediaSearchParams(
            per_page=config.anilist.per_page or 15,
            sort=["UPDATED_AT_DESC"],
            status_in=["RELEASING"]
        )

    handle_media_search_command(
        config=config,
        dump_json=dump_json,
        task_name="Fetching recently updated anime...",
        search_params_factory=create_search_params,
        empty_message="No recently updated anime found"
    )
    else:
        from sys import exit

        exit(1)
