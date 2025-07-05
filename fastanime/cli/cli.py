import click
from click.core import ParameterSource

from .. import __version__
from .config import AppConfig, ConfigLoader
from .constants import USER_CONFIG_PATH
from .options import options_from_model
from .utils.lazyloader import LazyGroup
from .utils.logging import setup_logging

commands = {
    "config": ".config",
}


@click.version_option(__version__, "--version")
@click.option("--no-config", is_flag=True, help="Don't load the user config file.")
@click.group(cls=LazyGroup, root="fastanime.cli.commands", lazy_subcommands=commands)
@options_from_model(AppConfig)
@click.pass_context
def cli(ctx: click.Context, no_config: bool, **kwargs):
    """
    The main entry point for the FastAnime CLI.
    """
    setup_logging(
        kwargs.get("log", False),
        kwargs.get("log_file", False),
        kwargs.get("rich_traceback", False),
    )

    loader = ConfigLoader(config_path=USER_CONFIG_PATH)
    config = AppConfig.model_validate({}) if no_config else loader.load()

    # update app config with command line parameters
    for param_name, param_value in ctx.params.items():
        source = ctx.get_parameter_source(param_name)
        if source == ParameterSource.COMMANDLINE:
            parameter = None
            for param in ctx.command.params:
                if param.name == param_name:
                    parameter = param
                    break
            if (
                parameter
                and hasattr(parameter, "model_name")
                and hasattr(parameter, "field_name")
            ):
                model_name = getattr(parameter, "model_name")
                field_name = getattr(parameter, "field_name")
                if hasattr(config, model_name):
                    model_instance = getattr(config, model_name)
                    if hasattr(model_instance, field_name):
                        setattr(model_instance, field_name, param_value)
    ctx.obj = config
