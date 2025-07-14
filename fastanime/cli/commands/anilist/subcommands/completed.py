from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from fastanime.core.config import AppConfig


@click.command(help="View anime you completed")
@click.option(
    "--dump-json",
    "-d",
    is_flag=True,
    help="Only print out the results dont open anilist menu",
)
@click.pass_obj
def completed(config: "AppConfig", dump_json: bool):
    from ..helpers import handle_user_list_command

    handle_user_list_command(
        config=config,
        dump_json=dump_json,
        status="COMPLETED",
        list_name="completed"
    )
