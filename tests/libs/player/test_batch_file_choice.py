"""Which file inside a season pack actually gets played.

Two bugs users hit: a "Season 1 + 2" pack played S02E02 when they asked for
episode 2 of season 1, and a "Complete Collection" played a bundled side arc
for episode 1 because it happened to come first in the torrent.
"""

from viu_media.libs.player.mpv.player import (
    _batch_target_season,
    _pick_batch_file_index,
    _torrent_file_index,
)


def _files(*names):
    return [{"name": n, "length": 100} for n in names]


def test_season_marker_is_read_from_the_magnet():
    assert _batch_target_season("magnet:?xt=urn:btih:ab&x.aniep=2&x.anisn=2") == 2
    # An older magnet without the marker means season 1.
    assert _batch_target_season("magnet:?xt=urn:btih:ab&x.aniep=2") == 1


def test_multi_season_pack_plays_the_requested_season():
    files = _files(
        "S01E01-One.mkv", "S01E02-Two.mkv", "S02E01-Three.mkv", "S02E02-Four.mkv"
    )
    assert files[_pick_batch_file_index(files, "2", 1)]["name"] == "S01E02-Two.mkv"
    assert files[_pick_batch_file_index(files, "2", 2)]["name"] == "S02E02-Four.mkv"


def test_end_to_end_through_the_magnet():
    files = _files("S01E01-One.mkv", "S01E02-Two.mkv", "S02E02-Four.mkv")
    magnet = "magnet:?xt=urn:btih:ab&x.aniep=2&x.anisn=2"
    assert files[_torrent_file_index(files, magnet)]["name"] == "S02E02-Four.mkv"


def test_bundled_arc_does_not_win_episode_one():
    files = _files(
        "[AT] Show Mugen Train Arc - 01.mkv",
        "[AT] Show - 01.mkv",
        "[AT] Show - 02.mkv",
        "[AT] Show - 03.mkv",
    )
    assert files[_pick_batch_file_index(files, "1", 1)]["name"] == "[AT] Show - 01.mkv"


def test_spinoff_short_never_outranks_the_real_episode():
    files = [
        {"name": "[AT] Show Junior High - 01.mkv", "length": 50_000_000},
        {"name": "[AT] Show - 01.mkv", "length": 1_400_000_000},
    ]
    assert files[_pick_batch_file_index(files, "1", 1)]["name"] == "[AT] Show - 01.mkv"


def test_unmatched_season_still_plays_something():
    """Better an odd pack than a dead menu entry."""
    files = _files("Show - 01.mkv", "Show - 02.mkv")
    assert _pick_batch_file_index(files, "2", 4) is not None
