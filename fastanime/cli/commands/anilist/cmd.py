import click

from ...interactive.session import session

commands = {
    "trending": "trending.trending",
    "recent": "recent.recent",
    "search": "search.search",
    "download": "download.download",
    "downloads": "downloads.downloads",
}


@click.command(name="anilist")
@click.option(
    "--resume", is_flag=True, help="Resume from the last session (Not yet implemented)."
)
@click.pass_context
def anilist(ctx: click.Context, resume: bool):
    """
    The entry point for the 'anilist' command. If no subcommand is invoked,
    it launches the interactive TUI mode.
    """

    config = ctx.obj

    if ctx.invoked_subcommand is None:
        session.load_menus_from_folder()
        session.run(config)
