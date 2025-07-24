import re
from typing import Dict, List, Optional, Union

# def _extract_episode_number(episode_string: str) -> int | None:
#     """
#     Extracts the episode number from a string formatted as 'Episode {number} - desc'.

#     Args:
#         episode_string: The input string, e.g., "Episode 123 - The Grand Finale".

#     Returns:
#         The extracted episode number as an integer, or None if the format
#         does not match.
#     """
#     match = EPISODE_PATTERN.search(episode_string)


#     if match:
#         episode_number_str = match.group(1)
#         return int(episode_number_str)
#     else:
#         return None
def extract_episode_number(title: str) -> Optional[float]:
    """
    Extracts the episode number (supports floats) from a title like:
    "Episode 2.5 - Some Title". Returns None if no match.
    """
    match = re.search(r"Episode\s+([0-9]+(?:\.[0-9]+)?)", title, re.IGNORECASE)
    if match:
        return round(float(match.group(1)), 3)
    return None


def strip_original_episode_prefix(title: str) -> str:
    """
    Removes the original 'Episode X' prefix from the title.
    """
    return re.sub(
        r"^Episode\s+[0-9]+(?:\.[0-9]+)?\s*[-:–]?\s*", "", title, flags=re.IGNORECASE
    )


def renumber_titles(titles: List[str]) -> Dict[str, Union[int, float, None]]:
    """
    Extracts and renumbers episode numbers from titles starting at 1.
    Preserves fractional spacing and leaves titles without episode numbers untouched.

    Returns a dict: {original_title: new_episode_number or None}
    """
    # Separate titles with and without numbers
    with_numbers = [(t, extract_episode_number(t)) for t in titles]
    with_numbers = [(t, n) for t, n in with_numbers if n is not None]
    without_numbers = [t for t in titles if extract_episode_number(t) is None]

    # Sort numerically
    with_numbers.sort(key=lambda x: x[1])

    renumbered = {}
    base_map = {}
    next_index = 1

    for title, orig_ep in with_numbers:
        int_part = int(orig_ep)
        is_whole = orig_ep == int_part

        if is_whole:
            base_map[int_part] = next_index
            renumbered_val = next_index
            next_index += 1
        else:
            base_val = base_map.get(int_part, next_index - 1)
            offset = round(orig_ep - int_part, 3)
            renumbered_val = round(base_val + offset, 3)

        renumbered[title] = (
            int(renumbered_val) if renumbered_val.is_integer() else renumbered_val
        )

    # Add back the unnumbered titles with `None`
    for t in without_numbers:
        renumbered[t] = None

    return renumbered
