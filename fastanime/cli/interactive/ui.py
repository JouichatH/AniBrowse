from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, Iterator, List, Optional

from rich import print as rprint
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from yt_dlp.utils import clean_html

from ...libs.anime.types import Anime

if TYPE_CHECKING:
    from ...core.config import AppConfig
    from ...libs.anilist.types import AnilistBaseMediaDataSchema
    from .session import Session


@contextlib.contextmanager
def progress_spinner(description: str = "Working...") -> Iterator[None]:
    """A context manager for showing a rich spinner for long operations."""
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    )
    task = progress.add_task(description=description, total=None)
    with progress:
        yield
    progress.remove_task(task)


def display_error(message: str) -> None:
    """Displays a formatted error message and waits for user confirmation."""
    rprint(f"[bold red]Error:[/] {message}")
    Confirm.ask("Press Enter to continue...", default=True, show_default=False)


def prompt_main_menu(session: Session, choices: list[str]) -> Optional[str]:
    """Displays the main menu using the session's selector."""
    header = (
        "🚀 FastAnime Interactive Menu"
        if session.config.general.icons
        else "FastAnime Interactive Menu"
    )
    return session.selector.choose("Select Action", choices, header=header)


def prompt_for_search(session: Session) -> Optional[str]:
    """Prompts the user for a search query using the session's selector."""
    search_term = session.selector.ask("Enter search term")
    return search_term if search_term and search_term.strip() else None


def prompt_anime_selection(
    session: Session, media_list: list[AnilistBaseMediaDataSchema]
) -> Optional[AnilistBaseMediaDataSchema]:
    """Displays anime results using the session's selector."""
    from yt_dlp.utils import sanitize_filename

    choice_map = {}
    for anime in media_list:
        title = anime.get("title", {}).get("romaji") or anime.get("title", {}).get(
            "english", "Unknown Title"
        )
        progress = anime.get("mediaListEntry", {}).get("progress", 0)
        episodes_total = anime.get("episodes") or "∞"
        display_title = sanitize_filename(f"{title} ({progress}/{episodes_total})")
        choice_map[display_title] = anime

    choices = list(choice_map.keys()) + ["Next Page", "Previous Page", "Back"]
    selection = session.selector.choose(
        "Select Anime", choices, header="Search Results"
    )

    if selection in ["Back", "Next Page", "Previous Page"] or selection is None:
        return selection  # Let the state handle these special strings

    return choice_map.get(selection)


def prompt_anime_actions(
    session: Session, anime: AnilistBaseMediaDataSchema
) -> Optional[str]:
    """Displays the actions menu for a selected anime."""
    choices = ["Stream", "View Info", "Back"]
    if anime.get("trailer"):
        choices.insert(0, "Watch Trailer")
    if session.config.user:
        choices.insert(1, "Add to List")
        choices.insert(2, "Score Anime")

    header = anime.get("title", {}).get("romaji", "Anime Actions")
    return session.selector.choose("Select Action", choices, header=header)


def prompt_episode_selection(
    session: Session, episode_list: list[str], anime_details: Anime
) -> Optional[str]:
    """Displays the list of available episodes."""
    choices = episode_list + ["Back"]
    header = f"Episodes for {anime_details.title}"
    return session.selector.choose("Select Episode", choices, header=header)


def prompt_add_to_list(session: Session) -> Optional[str]:
    """Prompts user to select an AniList media list status."""
    statuses = {
        "Watching": "CURRENT",
        "Planning": "PLANNING",
        "Completed": "COMPLETED",
        "Rewatching": "REPEATING",
        "Paused": "PAUSED",
        "Dropped": "DROPPED",
        "Back": None,
    }
    choice = session.selector.choose("Add to which list?", list(statuses.keys()))
    return statuses.get(choice) if choice else None


def display_anime_details(anime: AnilistBaseMediaDataSchema) -> None:
    """Renders a detailed view of an anime's information."""
    from click import clear

    from ...cli.utils.anilist import (
        extract_next_airing_episode,
        format_anilist_date_object,
        format_list_data_with_comma,
        format_number_with_commas,
    )

    clear()

    title_eng = anime.get("title", {}).get("english", "N/A")
    title_romaji = anime.get("title", {}).get("romaji", "N/A")

    content = (
        f"[bold cyan]English:[/] {title_eng}\n"
        f"[bold cyan]Romaji:[/] {title_romaji}\n\n"
        f"[bold]Status:[/] {anime.get('status', 'N/A')}  "
        f"[bold]Episodes:[/] {anime.get('episodes') or 'N/A'}\n"
        f"[bold]Score:[/] {anime.get('averageScore', 0) / 10.0} / 10\n"
        f"[bold]Popularity:[/] {format_number_with_commas(anime.get('popularity'))}\n\n"
        f"[bold]Genres:[/] {format_list_data_with_comma([g for g in anime.get('genres', [])])}\n"
        f"[bold]Tags:[/] {format_list_data_with_comma([t['name'] for t in anime.get('tags', [])[:5]])}\n\n"
        f"[bold]Airing:[/] {extract_next_airing_episode(anime.get('nextAiringEpisode'))}\n"
        f"[bold]Period:[/] {format_anilist_date_object(anime.get('startDate'))} to {format_anilist_date_object(anime.get('endDate'))}\n\n"
        f"[bold underline]Description[/]\n{clean_html(anime.get('description', 'No description available.'))}"
    )

    rprint(Panel(content, title="Anime Details", border_style="magenta"))
    Confirm.ask("Press Enter to return...", default=True, show_default=False)


def filter_by_quality(quality: str, stream_links: list, default=True):
    """(Moved from utils) Filters a list of streams by quality."""
    for stream_link in stream_links:
        q = float(quality)
        try:
            stream_q = float(stream_link.quality)
        except (ValueError, TypeError):
            continue
        if q - 80 <= stream_q <= q + 80:
            return stream_link
    if stream_links and default:
        return stream_links[0]
    return None
