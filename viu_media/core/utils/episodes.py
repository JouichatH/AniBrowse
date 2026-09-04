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

# Season declared by a file inside a pack: "S04E01" or a standalone "S02".
_FILE_SEASON_RE = re.compile(r"\bS0*(\d{1,2})(?:\s*E\s*\d{1,4})?\b", re.IGNORECASE)
# Bracketed group tags, CRC hashes and parenthetical notes - noise when working
# out which files in a pack belong to the same series.
_BRACKETED_RE = re.compile(r"[\[(][^\])]*[\])]")
_NOISE_RE = re.compile(r"[^a-z0-9]+")


def season_from_filename(name: str) -> "int | None":
    """The season a file declares, or None when it does not say."""
    if not name:
        return None
    m = _FILE_SEASON_RE.search(name)
    return int(m.group(1)) if m else None


def parse_release_name(name: str) -> "tuple[int | None, str | None]":
    """``(season, episode)`` a file name declares; either may be None."""
    return season_from_filename(name), episode_from_filename(name)


def series_key(name: str) -> str:
    """A pack file's series identity, with episode/season/noise stripped.

    Packs bundle several series under one torrent - a Demon Slayer collection
    holds "... Kimetsu no Yaiba - 01" next to "... Kimetsu no Yaiba Mugen Train
    Arc - 01", and both parse as episode 1. Grouping by this key separates
    them, so the main run can be told apart from an arc or a side story.
    """
    stem = name.rsplit(".", 1)[0] if "." in name else name
    stem = _BRACKETED_RE.sub(" ", stem)
    for pattern in _PATTERNS:
        stem = pattern.sub(" ", stem)
    stem = _FILE_SEASON_RE.sub(" ", stem)
    return _NOISE_RE.sub(" ", stem.lower()).strip()


def main_series_files(names: "list[str]", wanted_season: int = 1) -> "list[str]":
    """The files in a pack that belong to the season the user asked for.

    Three shapes, in order of how much they can be trusted:

    1. Files declare seasons ("S01E02") - keep the requested season. This is
       what stops a "Season 1 + 2" pack from answering "episode 2" with
       S02E02.
    2. They do not, but the pack bundles several series ("Mugen Train Arc")
       - keep the largest group, which is the main run. Without this, episode 1
       resolved to a side story purely because it came first in the file table.
    3. Neither - keep everything.
    """
    # Parse once and keep the numbers: re-deriving them later loses the fact
    # that every survivor is known to have one.
    parsed: "dict[str, float]" = {}
    for n in names:
        episode = episode_from_filename(n)
        if episode is not None and not is_extra_file(n):
            parsed[n] = float(episode)
    usable = list(parsed)
    if not usable:
        return []

    seasoned = [n for n in usable if season_from_filename(n) is not None]
    if seasoned:
        wanted = [n for n in seasoned if season_from_filename(n) == wanted_season]
        if wanted:
            return wanted
        unseasoned = [n for n in usable if season_from_filename(n) is None]
        if not unseasoned:
            # The pack simply does not carry the season that was asked for.
            return []
        usable = unseasoned

    # Only disambiguate when there is something ambiguous. If every episode
    # number occurs once, the pack holds one run and grouping can only do
    # harm: packs that name files by episode title ("Bleach - 042 - The Ichimaru
    # Gin Rebellion") give every file its own key, and picking the "largest
    # group" there threw away 361 of 366 episodes.
    counts: dict = {}
    for n in usable:
        counts[parsed[n]] = counts.get(parsed[n], 0) + 1
    if max(counts.values()) == 1:
        return usable

    groups: dict = {}
    for n in usable:
        groups.setdefault(series_key(n), []).append(n)
    if len(groups) == 1:
        return usable
    # Numbers collide, so the pack really does bundle several runs. The largest
    # group is the main one; ties break toward the run starting lowest, which
    # is the original rather than a continuation.
    return max(
        groups.values(),
        key=lambda g: (len(g), -min(parsed[n] for n in g)),
    )
