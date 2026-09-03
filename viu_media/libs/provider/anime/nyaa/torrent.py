"""Read a season pack's episode list out of its ``.torrent`` file.

Most completed shows reach nyaa only as a season pack, and packs that spell the
range out in the title ("(01-28)") are the minority. The rest say "S01", "Batch"
or "Complete Series" and keep the real episode list where it actually lives -
inside the torrent's file table. Without reading that, back-catalogue shows look
like they have *no episodes at all*: nyaa returns 75 real results for "Shingeki
no Kyojin" and the provider used to build an empty menu from them.

nyaa's RSS gives a direct HTTPS ``.torrent`` link per entry, so one small GET
(~100KB) and a bencode parse yields the exact episode numbers. No P2P, no DHT,
no extra dependency - bencode is about thirty lines.
"""

from __future__ import annotations

import logging
from typing import Any, List, Tuple

from .....core.utils.episodes import episode_from_filename, is_extra_file

logger = logging.getLogger(__name__)

#: Refuse absurd torrents rather than parsing megabytes of bencode.
MAX_TORRENT_BYTES = 4 * 1024 * 1024

_VIDEO_SUFFIXES = (".mkv", ".mp4", ".avi", ".m4v", ".webm", ".ts")


def _bdecode(data: bytes, i: int = 0) -> Tuple[Any, int]:
    """Minimal bencode reader: ints, byte strings, lists and dicts."""
    marker = data[i : i + 1]
    if marker == b"i":
        end = data.index(b"e", i)
        return int(data[i + 1 : end]), end + 1
    if marker == b"l":
        items: List[Any] = []
        i += 1
        while data[i : i + 1] != b"e":
            value, i = _bdecode(data, i)
            items.append(value)
        return items, i + 1
    if marker == b"d":
        mapping: dict = {}
        i += 1
        while data[i : i + 1] != b"e":
            key, i = _bdecode(data, i)
            value, i = _bdecode(data, i)
            mapping[key] = value
        return mapping, i + 1
    colon = data.index(b":", i)
    length = int(data[i:colon])
    start = colon + 1
    return data[start : start + length], start + length


def torrent_file_names(content: bytes) -> List[str]:
    """Every file name inside a ``.torrent``, single-file torrents included."""
    if not content or len(content) > MAX_TORRENT_BYTES or content[:1] != b"d":
        return []
    try:
        meta, _ = _bdecode(content)
        info = meta[b"info"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        logger.debug("could not parse .torrent: %s", e)
        return []

    def _text(raw: bytes) -> str:
        return raw.decode("utf-8", "replace")

    files = info.get(b"files")
    if not files:
        name = info.get(b"name")
        return [_text(name)] if name else []

    names: List[str] = []
    for entry in files:
        try:
            path = entry[b"path"]
        except (KeyError, TypeError):
            continue
        if path:
            names.append(_text(path[-1]))
    return names


def torrent_episodes(content: bytes) -> List[str]:
    """Sorted episode numbers a pack contains, read from its video files.

    Only video files count: a pack's NCOP/NCED extras and its ``.nfo`` would
    otherwise contribute phantom episodes to the menu.
    """
    main: set = set()
    extras: set = set()
    for name in torrent_file_names(content):
        if not name.lower().endswith(_VIDEO_SUFFIXES):
            continue
        episode = episode_from_filename(name)
        if episode is None:
            continue
        (extras if is_extra_file(name) else main).add(episode)
    # Bundled spin-offs and OVAs reuse episode numbers; counting them would
    # claim episodes the main show does not have. They still stand in when a
    # pack holds nothing else.
    return sorted(main or extras, key=float)
