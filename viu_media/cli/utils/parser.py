"""Episode range parsing utilities for Ani-Browse CLI commands."""

from typing import Iterator

from ...core.exceptions import InvalidEpisodeRangeError


def _index(value: str, range_str: str, label: str) -> int:
    """Parse one slice index, rejecting negatives.

    The values are 0-based indices into the episode list, never Python's
    negative wrap-around indices: a stray "-2:" would silently download the
    last two episodes instead of erroring, so treat any negative as invalid.
    """
    try:
        idx = int(value)
    except ValueError as e:
        raise InvalidEpisodeRangeError(
            f"Invalid episode range format: '{range_str}'. "
            f"{label} must be a valid integer."
        ) from e
    if idx < 0:
        raise InvalidEpisodeRangeError(
            f"Invalid episode range format: '{range_str}'. "
            f"{label} must not be negative."
        )
    return idx


def parse_episode_range(
    episode_range_str: str | None, available_episodes: list[str]
) -> Iterator[str]:
    """
    Parse an episode range string and return an iterator of episode numbers.

    This function handles various episode range formats:
    - Single episode: "5" -> episodes from index 5 onwards
    - Range with start and end: "5:10" -> episodes from index 5 to 10 (exclusive)
    - Range with step: "5:10:2" -> episodes from index 5 to 10 with step 2
    - Start only: "5:" -> episodes from index 5 onwards
    - End only: ":10" -> episodes from beginning to index 10
    - All episodes: ":" -> all episodes

    Args:
        episode_range_str: The episode range string to parse (e.g., "5:10", "5:", ":10", "5")
        available_episodes: List of available episode numbers/identifiers

    Returns:
        Iterator over the selected episode numbers

    Raises:
        ValueError: If the episode range format is invalid
        IndexError: If the specified indices are out of range

    Examples:
        >>> episodes = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
        >>> list(parse_episode_range("2:5", episodes))
        ['3', '4', '5']
        >>> list(parse_episode_range("5:", episodes))
        ['6', '7', '8', '9', '10']
        >>> list(parse_episode_range(":3", episodes))
        ['1', '2', '3']
        >>> list(parse_episode_range("2:8:2", episodes))
        ['3', '5', '7']
    """
    if not episode_range_str:
        # No range specified, return all episodes
        return iter(available_episodes)

    # Sort episodes numerically for consistent ordering
    episodes = sorted(available_episodes, key=float)

    if ":" in episode_range_str:
        # Handle colon-separated ranges
        parts = episode_range_str.split(":")

        if len(parts) == 3:
            # Format: start:end:step
            start_str, end_str, step_str = parts
            if not all([start_str, end_str, step_str]):
                raise ValueError(
                    f"Invalid episode range format: '{episode_range_str}'. "
                    "When using 3 parts (start:end:step), all parts must be non-empty."
                )

            start_idx = _index(start_str, episode_range_str, "Start")
            end_idx = _index(end_str, episode_range_str, "End")
            step = _index(step_str, episode_range_str, "Step")
            if step <= 0:
                raise InvalidEpisodeRangeError(
                    f"Invalid episode range format: '{episode_range_str}'. "
                    "Step value must be positive."
                )
            return iter(episodes[start_idx:end_idx:step])

        elif len(parts) == 2:
            # Format: start:end or start: or :end
            start_str, end_str = parts

            if start_str and end_str:
                # Both start and end specified: start:end
                start_idx = _index(start_str, episode_range_str, "Start")
                end_idx = _index(end_str, episode_range_str, "End")
                return iter(episodes[start_idx:end_idx])

            elif start_str and not end_str:
                # Only start specified: start:
                start_idx = _index(start_str, episode_range_str, "Start")
                return iter(episodes[start_idx:])

            elif not start_str and end_str:
                # Only end specified: :end
                end_idx = _index(end_str, episode_range_str, "End")
                return iter(episodes[:end_idx])

            else:
                # Both empty: ":"
                return iter(episodes)
        else:
            raise ValueError(
                f"Invalid episode range format: '{episode_range_str}'. "
                "Too many colon separators."
            )
    else:
        # Single number: start from that index onwards
        start_idx = _index(episode_range_str, episode_range_str, "Value")
        return iter(episodes[start_idx:])
