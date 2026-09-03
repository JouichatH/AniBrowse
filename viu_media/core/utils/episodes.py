"""Read an episode number out of a release / file name.

Fansub packs are named half a dozen ways and the two places that care - the
nyaa provider building an episode menu, and the player picking one file out of
a season pack - must agree, or the menu offers an episode the player cannot
find. Hence one parser, shared.

Handled forms, most specific first::

    Show.S04E01.1080p.mkv        -> "1"    (scene naming)
    Show - 03 [1080p].mkv        -> "3"    (fansub naming)
    Show - 07.5 (OVA).mkv        -> "7.5"  (half episodes)
    Show_12_[Group].mkv          -> "12"
    Show EP08.mkv / Show E08.mkv -> "8"

Deliberately NOT handled: a bare number anywhere in the name. "Show 2024.mkv"
and "[Group] Show 1080p.mkv" would both match and silently play the wrong file,
which is worse than admitting we do not know.
"""

from __future__ import annotations

import re

# "S04E01" / "s4e1" - the season is matched so it cannot be read as the episode.
_SXXEYY_RE = re.compile(r"\bS\d{1,2}\s*E\s*0*(\d{1,4}(?:\.\d+)?)\b", re.IGNORECASE)
# " - 03 ", " - 03v2 (", " - 7.5." - the classic fansub separator.
_DASH_EP_RE = re.compile(r"\s-\s0*(\d+(?:\.\d+)?)(?:v\d+)?(?=\s|$|\(|\[|\.)")
# "_12_" / "_12." - underscore-delimited, common in scene releases.
_USCORE_EP_RE = re.compile(r"_0*(\d{1,4}(?:\.\d+)?)(?:v\d+)?(?=_|\.|$)")
# "EP08" / "E08" as a standalone token.
_EP_TOKEN_RE = re.compile(r"\bE(?:P|PISODE)?\s*0*(\d{1,4}(?:\.\d+)?)\b", re.IGNORECASE)

_PATTERNS = (_SXXEYY_RE, _DASH_EP_RE, _USCORE_EP_RE, _EP_TOKEN_RE)


def episode_from_filename(name: str) -> str | None:
    """The episode number a release/file name declares, or None if it doesn't.

    Returns the number as a string with leading zeros stripped ("01" -> "1")
    and a trailing ".0" removed, so it compares equal to the episode ids the
    menus use.
    """
    if not name:
        return None
    for pattern in _PATTERNS:
        m = pattern.search(name)
        if m:
            value = m.group(1)
            if value.endswith(".0"):
                value = value[:-2]
            # Strip leading zeros without turning "0" into "".
            return str(int(float(value))) if float(value).is_integer() else value
    return None

# Bundled content that shares episode numbers with the main show. A "Complete
# Collection" of Attack on Titan carries "Junior High - 01" (a 7-minute parody
# spin-off) alongside "Attack on Titan - 01"; picking the wrong one plays the
# wrong series entirely. These files are real content, so they are ranked last
# rather than hidden - a pack that holds ONLY specials still resolves.
_EXTRA_RE = re.compile(
    r"\b(?:junior\s*high|OVA|OAD|ONA|special|specials|SP|movie|film|recap"
    r"|omake|extra|bonus|picture\s*drama|NC(?:OP|ED)|clean\s*(?:op|ed)"
    r"|opening|ending|PV|CM|menu|trailer|preview)\b",
    re.IGNORECASE,
)


def is_extra_file(name: str) -> bool:
    """Whether a file inside a pack is bundled extra content, not the show."""
    return bool(_EXTRA_RE.search(name or ""))
