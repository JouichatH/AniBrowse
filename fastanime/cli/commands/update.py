"""Update command for FastAnime CLI."""

import sys
from typing import TYPE_CHECKING

import click
from rich import print
from rich.console import Console
from rich.markdown import Markdown

from ..utils.update import check_for_updates, update_app

if TYPE_CHECKING:
    from ...core.config import AppConfig


@click.command(
    help="Update FastAnime to the latest version",
    short_help="Update FastAnime",
    epilog="""
\b
\b\bExamples:
  # Check for updates and update if available
  fastanime update
\b
  # Force update even if already up to date
  fastanime update --force
\b
  # Only check for updates without updating
  fastanime update --check-only
\b
  # Show release notes for the latest version
  fastanime update --release-notes
""",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force update even if already up to date",
)
@click.option(
    "--check-only",
    "-c",
    is_flag=True,
    help="Only check for updates without updating",
)
@click.option(
    "--release-notes",
    "-r",
    is_flag=True,
    help="Show release notes for the latest version",
)
@click.pass_context
@click.pass_obj
def update(
    config: "AppConfig",
    ctx: click.Context,
    force: bool,
    check_only: bool,
    release_notes: bool,
) -> None:
    """
    Update FastAnime to the latest version.

    This command checks for available updates and optionally updates
    the application to the latest version from the configured sources
    (pip, uv, pipx, git, or nix depending on installation method).

    Args:
        config: The application configuration object
        ctx: The click context containing CLI options
        force: Whether to force update even if already up to date
        check_only: Whether to only check for updates without updating
        release_notes: Whether to show release notes for the latest version
    """
    try:
        if release_notes:
            print("[cyan]Fetching latest release notes...[/]")
            is_latest, release_json = check_for_updates()

            if not release_json:
                print(
                    "[yellow]Could not fetch release information. Please check your internet connection.[/]"
                )
                sys.exit(1)

            version = release_json.get("tag_name", "unknown")
            release_name = release_json.get("name", version)
            release_body = release_json.get("body", "No release notes available.")
            published_at = release_json.get("published_at", "unknown")

            console = Console()

            print(f"[bold cyan]Release: {release_name}[/]")
            print(f"[dim]Version: {version}[/]")
            print(f"[dim]Published: {published_at}[/]")
            print()

            # Display release notes as markdown if available
            if release_body.strip():
                markdown = Markdown(release_body)
                console.print(markdown)
            else:
                print("[dim]No release notes available for this version.[/]")

            return

        elif check_only:
            print("[cyan]Checking for updates...[/]")
            is_latest, release_json = check_for_updates()

            if not release_json:
                print(
                    "[yellow]Could not check for updates. Please check your internet connection.[/]"
                )
                sys.exit(1)

            if is_latest:
                print("[green]FastAnime is up to date![/]")
                print(
                    f"[dim]Current version: {release_json.get('tag_name', 'unknown')}[/]"
                )
            else:
                latest_version = release_json.get("tag_name", "unknown")
                print(f"[yellow]Update available: {latest_version}[/]")
                print("[dim]Run 'fastanime update' to update[/]")
                sys.exit(1)
        else:
            print("[cyan]Checking for updates and updating if necessary...[/]")
            success, release_json = update_app(force=force)

            if not release_json:
                print(
                    "[red]Could not check for updates. Please check your internet connection.[/]"
                )
                sys.exit(1)

            if success:
                latest_version = release_json.get("tag_name", "unknown")
                print(f"[green]Successfully updated to version {latest_version}![/]")
            else:
                if force:
                    print(
                        "[red]Update failed. Please check the error messages above.[/]"
                    )
                    sys.exit(1)
                # If not forced and update failed, it might be because already up to date
                # The update_app function already prints appropriate messages

    except KeyboardInterrupt:
        print("\n[yellow]Update cancelled by user.[/]")
        sys.exit(1)
    except Exception as e:
        print(f"[red]An error occurred during update: {e}[/]")
        # Get trace option from parent context
        trace = ctx.parent.params.get("trace", False) if ctx.parent else False
        if trace:
            raise
        sys.exit(1)
