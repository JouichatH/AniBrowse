import re
from typing import TYPE_CHECKING, List, Optional

from yt_dlp.utils import clean_html as ytdlp_clean_html

from ...libs.api.types import AiringSchedule, MediaItem

COMMA_REGEX = re.compile(r"([0-9]{3})(?=\d)")


def clean_html(raw_html: str) -> str:
    """A wrapper around yt-dlp's clean_html to handle None inputs."""
    return ytdlp_clean_html(raw_html) if raw_html else ""


def format_number_with_commas(number: Optional[int]) -> str:
    """Formats an integer with commas for thousands separation."""
    if number is None:
        return "N/A"
    return COMMA_REGEX.sub(r"\1,", str(number)[::-1])[::-1]


def format_airing_schedule(airing: Optional[AiringSchedule]) -> str:
    """Formats the next airing episode information into a readable string."""
    if not airing or not airing.airing_at:
        return "N/A"

    # Get a human-readable date and time
    air_date = airing.airing_at.strftime("%a, %b %d at %I:%M %p")
    return f"Ep {airing.episode} on {air_date}"


def format_genres(genres: List[str]) -> str:
    """Joins a list of genres into a single, comma-separated string."""
    return ", ".join(genres) if genres else "N/A"


def format_score_stars_full(score: Optional[float]) -> str:
    """Formats an AniList score (0-100) to a 0-10 scale using full stars."""
    if score is None:
        return "N/A"

    # Convert 0-100 to 0-10, then to a whole number of stars
    num_stars = min(round(score * 6 / 100), 6)
    return "⭐" * num_stars


def format_score(score: Optional[float]) -> str:
    """Formats an AniList score (0-100) to a 0-10 scale."""
    if score is None:
        return "N/A"
    return f"{score / 10.0:.1f} / 10"


def shell_safe(text: Optional[str]) -> str:
    """
    Escapes a string for safe inclusion in a shell script,
    specifically for use within double quotes. It escapes backticks,
    double quotes, and dollar signs.
    """
    if not text:
        return ""
    return text.replace("`", "\\`").replace('"', '\\"').replace("$", "\\$")
