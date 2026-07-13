"""Tests for the AniList tag/genre mapping - the paths crash-patched twice.

AniList adds genres/tags over time while our generated enums lag; an unknown
value must be skipped, never raise and fail the whole request.
"""

from viu_media.libs.media_api.anilist.mapper import _to_generic_tags
from viu_media.libs.media_api.types import MediaGenre, MediaTag


def test_unknown_tags_skipped_known_kept():
    tags = [
        {"name": "Time Skip", "rank": 90},  # known
        {"name": "Totally Invented Tag That Does Not Exist", "rank": 50},
        {"name": None},
        None,
        {"name": "Female Harem", "rank": 30},  # known
    ]
    items = _to_generic_tags(tags)  # type: ignore[arg-type]
    names = {i.name for i in items}
    # No exception; only enum-valid tags survive.
    assert MediaTag("Time Skip") in names
    assert MediaTag("Female Harem") in names
    assert len(items) == 2


def test_empty_or_none_tags_return_empty():
    assert _to_generic_tags(None) == []  # type: ignore[arg-type]
    assert _to_generic_tags([]) == []


def test_tag_rank_preserved():
    items = _to_generic_tags([{"name": "Time Skip", "rank": 77}])  # type: ignore[arg-type]
    assert items[0].rank == 77


def test_genre_filtering_is_membership_based():
    # Mirrors the mapper's genre comprehension: unknown genres are filtered out.
    raw = ["Action", "Not A Genre", "Comedy"]
    mapped = [
        MediaGenre(g) for g in raw if g in MediaGenre._value2member_map_
    ]
    assert mapped == [MediaGenre.ACTION, MediaGenre.COMEDY]
