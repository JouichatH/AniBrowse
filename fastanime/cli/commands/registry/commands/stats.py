"""
Registry stats command - show detailed statistics about the local registry
"""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .....core.config import AppConfig
from ....service.registry.service import MediaRegistryService
from ....utils.feedback import create_feedback_manager


@click.command(help="Show detailed statistics about the local media registry")
@click.option(
    "--detailed",
    "-d",
    is_flag=True,
    help="Show detailed breakdown by genre, format, and year",
)
@click.option(
    "--json", "output_json", is_flag=True, help="Output statistics in JSON format"
)
@click.option(
    "--api",
    default="anilist",
    type=click.Choice(["anilist"], case_sensitive=False),
    help="Media API to show stats for",
)
@click.pass_obj
def stats(config: AppConfig, detailed: bool, output_json: bool, api: str):
    """
    Display comprehensive statistics about your local media registry.

    Shows total counts, status breakdown, and optionally detailed
    analysis by genre, format, and release year.
    """
    feedback = create_feedback_manager(config.general.icons)
    console = Console()

    try:
        registry_service = MediaRegistryService(api, config.registry)
        stats_data = registry_service.get_registry_stats()

        if output_json:
            import json

            print(json.dumps(stats_data, indent=2, default=str))
            return

        _display_stats_overview(console, stats_data, api, config.general.icons)

        if detailed:
            _display_detailed_stats(console, stats_data, config.general.icons)

    except Exception as e:
        feedback.error("Stats Error", f"Failed to generate statistics: {e}")
        raise click.Abort()


def _display_stats_overview(console: Console, stats: dict, api: str, icons: bool):
    """Display basic registry statistics overview."""

    # Main overview panel
    overview_text = f"[bold cyan]Media API:[/bold cyan] {api.title()}\n"
    overview_text += (
        f"[bold cyan]Total Media:[/bold cyan] {stats.get('total_media', 0)}\n"
    )
    overview_text += (
        f"[bold cyan]Registry Version:[/bold cyan] {stats.get('version', 'Unknown')}\n"
    )
    overview_text += (
        f"[bold cyan]Last Updated:[/bold cyan] {stats.get('last_updated', 'Never')}\n"
    )
    overview_text += (
        f"[bold cyan]Storage Size:[/bold cyan] {stats.get('storage_size', 'Unknown')}"
    )

    panel = Panel(
        overview_text,
        title=f"{'📊 ' if icons else ''}Registry Overview",
        border_style="cyan",
    )
    console.print(panel)
    console.print()

    # Status breakdown table
    status_breakdown = stats.get("status_breakdown", {})
    if status_breakdown:
        table = Table(title=f"{'📋 ' if icons else ''}Status Breakdown")
        table.add_column("Status", style="cyan", no_wrap=True)
        table.add_column("Count", style="magenta", justify="right")
        table.add_column("Percentage", style="green", justify="right")

        total = sum(status_breakdown.values())
        for status, count in sorted(status_breakdown.items()):
            percentage = (count / total * 100) if total > 0 else 0
            table.add_row(status.title(), str(count), f"{percentage:.1f}%")

        console.print(table)
        console.print()

    # Download status breakdown
    download_stats = stats.get("download_stats", {})
    if download_stats:
        table = Table(title=f"{'💾 ' if icons else ''}Download Status")
        table.add_column("Status", style="cyan", no_wrap=True)
        table.add_column("Count", style="magenta", justify="right")

        for status, count in download_stats.items():
            table.add_row(status.title(), str(count))

        console.print(table)
        console.print()


def _display_detailed_stats(console: Console, stats: dict, icons: bool):
    """Display detailed breakdown by various categories."""

    # Genre breakdown
    genre_breakdown = stats.get("genre_breakdown", {})
    if genre_breakdown:
        table = Table(title=f"{'🎭 ' if icons else ''}Top Genres")
        table.add_column("Genre", style="cyan")
        table.add_column("Count", style="magenta", justify="right")

        # Sort by count and show top 10
        top_genres = sorted(genre_breakdown.items(), key=lambda x: x[1], reverse=True)[
            :10
        ]
        for genre, count in top_genres:
            table.add_row(genre, str(count))

        console.print(table)
        console.print()

    # Format breakdown
    format_breakdown = stats.get("format_breakdown", {})
    if format_breakdown:
        table = Table(title=f"{'📺 ' if icons else ''}Format Breakdown")
        table.add_column("Format", style="cyan")
        table.add_column("Count", style="magenta", justify="right")
        table.add_column("Percentage", style="green", justify="right")

        total = sum(format_breakdown.values())
        for format_type, count in sorted(format_breakdown.items()):
            percentage = (count / total * 100) if total > 0 else 0
            table.add_row(format_type, str(count), f"{percentage:.1f}%")

        console.print(table)
        console.print()

    # Year breakdown
    year_breakdown = stats.get("year_breakdown", {})
    if year_breakdown:
        table = Table(title=f"{'📅 ' if icons else ''}Release Years (Top 10)")
        table.add_column("Year", style="cyan", justify="center")
        table.add_column("Count", style="magenta", justify="right")

        # Sort by year descending and show top 10
        top_years = sorted(year_breakdown.items(), key=lambda x: x[0], reverse=True)[
            :10
        ]
        for year, count in top_years:
            table.add_row(str(year), str(count))

        console.print(table)
        console.print()

    # Rating breakdown
    rating_breakdown = stats.get("rating_breakdown", {})
    if rating_breakdown:
        table = Table(title=f"{'⭐ ' if icons else ''}Score Distribution")
        table.add_column("Score Range", style="cyan")
        table.add_column("Count", style="magenta", justify="right")

        for score_range, count in sorted(rating_breakdown.items()):
            table.add_row(score_range, str(count))

        console.print(table)
        console.print()
