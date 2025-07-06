import click

from ...interactive.anilist.controller import InteractiveController

# Import the new interactive components
from ...interactive.session import Session
from ...utils.lazyloader import LazyGroup

# Define your subcommands (this part remains the same)
commands = {
    "trending": "trending.trending",
    "recent": "recent.recent",
    "search": "search.search",
    # ... add all your other subcommands
}


@click.group(
    lazy_subcommands=commands,
    cls=LazyGroup(root="fastanime.cli.commands.anilist.subcommands"),
    invoke_without_command=True,
    help="A beautiful interface that gives you access to a complete streaming experience",
    short_help="Access all streaming options",
    epilog="""
\b
\b\bExamples:
  # Launch the interactive TUI
  fastanime anilist
\b
  # Run a specific subcommand
  fastanime anilist trending --dump-json
""",
)
@click.option(
    "--resume", is_flag=True, help="Resume from the last session (Not yet implemented)."
)
@click.pass_context
def anilist(ctx: click.Context, resume: bool):
    """
    The entry point for the 'anilist' command. If no subcommand is invoked,
    it launches the interactive TUI mode.
    """
    from ....libs.anilist.api import AniListApi

    config = ctx.obj

    # Initialize the AniList API client.
    anilist_client = AniListApi()
    if user := getattr(config, "user", None):  # Safely access user attribute
        anilist_client.update_login_info(user, user["token"])

    if ctx.invoked_subcommand is None:
        # ---- LAUNCH INTERACTIVE MODE ----

        # 1. Create the session object.
        session = Session(config, anilist_client)

        # 2. Handle resume logic (placeholder for now).
        if resume:
            click.echo(
                "Resume functionality is not yet implemented in the new architecture.",
                err=True,
            )
            # You would load session.state from a file here.

        # 3. Initialize and run the controller.
        controller = InteractiveController(session)

        # Clear the screen for a clean TUI experience.
        click.clear()
        controller.run()

        # Print a goodbye message on exit.
        click.echo("Exiting FastAnime. Have a great day!")
