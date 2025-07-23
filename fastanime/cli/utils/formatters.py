import re
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from yt_dlp.utils import clean_html as ytdlp_clean_html

from ...libs.api.types import AiringSchedule, MediaItem

COMMA_REGEX = re.compile(r"([0-9]{3})(?=\d)")


def format_media_duration(total_minutes: Optional[int]) -> str:
    """
    Converts a duration in minutes into a more human-readable format
    (e.g., "1 hour 30 minutes", "45 minutes", "2 hours").

    Args:
        total_minutes: The total duration in minutes (integer).

    Returns:
        A string representing the formatted duration.
    """
    if not total_minutes:
        return "N/A"

    if not isinstance(total_minutes, int) or total_minutes < 0:
        raise ValueError("Input must be a non-negative integer representing minutes.")

    if total_minutes == 0:
        return "0 minutes"

    hours = total_minutes // 60
    minutes = total_minutes % 60

    parts = []

    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours > 1 else ''}")

    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")

    # Join the parts with " and " if both hours and minutes are present
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    elif len(parts) == 1:
        return parts[0]
    else:
        # This case should ideally not be reached if total_minutes > 0
        return "0 minutes"  # Fallback for safety, though handled by initial check


def format_date(dt: Optional[datetime], format_str: str = "%A, %d %B %Y") -> str:
    """
    Formats a datetime object to a readable string.

    Default format: '2025-22 July'

    Params:
        dt (datetime): The datetime object to format.
        format_str (str): Optional custom format string (defaults to "%Y-%d %B").

    Returns:
        str: The formatted date.
    """
    if not dt:
        return "N/A"
    return dt.strftime(format_str)


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


def format_list_with_commas(list_of_strs: List[str]) -> str:
    """Joins a list of genres into a single, comma-separated string."""
    return ", ".join(list_of_strs) if list_of_strs else "N/A"


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
