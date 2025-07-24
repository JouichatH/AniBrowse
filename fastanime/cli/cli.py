from typing import TYPE_CHECKING

import click
from click.core import ParameterSource

from ..core.config import AppConfig
from ..core.constants import PROJECT_NAME, USER_CONFIG_PATH, __version__
from .config import ConfigLoader
from .options import options_from_model
from .utils.exception import setup_exceptions_handler
from .utils.lazyloader import LazyGroup
from .utils.logging import setup_logging

if TYPE_CHECKING:
    from typing import TypedDict

    from typing_extensions import Unpack

    class Options(TypedDict):
        no_config: bool | None
        trace: bool | None
        log_to_file: bool | None
        dev: bool | None
        log: bool | None
        rich_traceback: bool | None
        rich_traceback_theme: str


commands = {
    "config": "config.config",
    "search": "search.search",
    "anilist": "anilist.anilist",
    "download": "download.download",
    "update": "update.update",
}


@click.group(
    cls=LazyGroup,
    root="fastanime.cli.commands",
    lazy_subcommands=commands,
    context_settings=dict(auto_envvar_prefix=PROJECT_NAME),
)
@click.version_option(__version__, "--version")
@click.option("--no-config", is_flag=True, help="Don't load the user config file.")
@click.option(
    "--trace", is_flag=True, help="Controls Whether to display tracebacks or not"
)
@click.option("--dev", is_flag=True, help="Controls Whether the app is in dev mode")
@click.option("--log", is_flag=True, help="Controls Whether to log")
@click.option("--log-to-file", is_flag=True, help="Controls Whether to log to a file")
@click.option(
    "--rich-traceback",
    is_flag=True,
    help="Controls Whether to display a rich traceback",
)
@click.option(
    "--rich-traceback-theme",
    default="github-dark",
    help="Controls Whether to display a rich traceback",
)
@options_from_model(AppConfig)
@click.pass_context
def cli(ctx: click.Context, **options: "Unpack[Options]"):
    """
    The main entry point for the FastAnime CLI.
    """
    setup_logging(options["log"], options["log_to_file"])
    setup_exceptions_handler(
        options["trace"],
        options["dev"],
        options["rich_traceback"],
        options["rich_traceback_theme"],
    )

    cli_overrides = {}
    param_lookup = {p.name: p for p in ctx.command.params}

    for param_name, param_value in ctx.params.items():
        source = ctx.get_parameter_source(param_name)
        if source in (ParameterSource.ENVIRONMENT, ParameterSource.COMMANDLINE):
            parameter = param_lookup.get(param_name)

            if (
                parameter
                and hasattr(parameter, "model_name")
                and hasattr(parameter, "field_name")
            ):
                model_name = getattr(parameter, "model_name")
                field_name = getattr(parameter, "field_name")

                if model_name not in cli_overrides:
                    cli_overrides[model_name] = {}
                cli_overrides[model_name][field_name] = param_value

    loader = ConfigLoader(config_path=USER_CONFIG_PATH)
    config = (
        AppConfig.model_validate(cli_overrides)
        if options["no_config"]
        else loader.load(cli_overrides)
    )
    ctx.obj = config
