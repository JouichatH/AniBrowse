from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from fastanime.core.config import AppConfig


@click.command(
    help="Fetch the top 15 anime that are currently trending",
    short_help="Trending anime 🔥🔥🔥",
)
@click.option(
    "--dump-json",
    "-d",
    is_flag=True,
    help="Only print out the results dont open anilist menu",
)
@click.pass_obj
def trending(config: "AppConfig", dump_json: bool):
    from fastanime.libs.api.params import ApiSearchParams
    from ..helpers import handle_media_search_command

    def create_search_params(config):
        return ApiSearchParams(
            per_page=config.anilist.per_page or 15,
            sort=["TRENDING_DESC"]
        )

    handle_media_search_command(
        config=config,
        dump_json=dump_json,
        task_name="Fetching trending anime...",
        search_params_factory=create_search_params,
        empty_message="No trending anime found"
    )
