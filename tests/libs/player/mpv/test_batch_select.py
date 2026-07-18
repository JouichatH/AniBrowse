"""Tests for selecting one episode's file out of a nyaa batch torrent.

The pure pieces - reading the ``&x.aniep=`` magnet marker, parsing an episode
number out of a fansub file name, and mapping a target episode to the file
index ``webtorrent --select`` expects - are exercised here. The network/P2P
boundary (``_resolve_batch_file``'s webtorrent subprocess calls) is not.
"""

from viu_media.libs.player.mpv.player import (
    _batch_target_episode,
    _file_episode,
    _magnet_info_hash,
    _pick_batch_file_index,
    _stream_file_url,
    _valid_torrent_file,
    _xs_url,
)

# A real SubsPlease batch file list (names only), in torrent order.
_FRIEREN_FILES = [
    {"name": f"[SubsPlease] Sousou no Frieren - {n:02d}v3 (1080p) [ABCD].mkv"}
    for n in range(1, 29)
]


def test_batch_target_episode_reads_marker():
    assert _batch_target_episode("magnet:?xt=urn:btih:abc&dn=x&x.aniep=7") == "7"
    assert _batch_target_episode("magnet:?xt=urn:btih:abc&x.aniep=12.5") == "12.5"


def test_batch_target_episode_absent_is_none():
    # A plain single-episode magnet carries no marker.
    assert _batch_target_episode("magnet:?xt=urn:btih:abc&dn=Foo+-+03") is None
    assert _batch_target_episode("") is None


def test_file_episode_parses_fansub_names():
    assert _file_episode("[SubsPlease] Sousou no Frieren - 07v2 (1080p) [X].mkv") == "7"
    assert _file_episode("[Erai-raws] Show - 12 [1080p].mkv") == "12"
    assert _file_episode("[G] Movie - 5.5 (720p).mkv") == "5.5"
    # An NCOP/NCED or a batch folder name has no " - NN" episode token.
    assert _file_episode("[SubsPlease] Show (01-28) (1080p) [Batch]") is None


def test_pick_index_matches_by_number_not_position():
    assert _pick_batch_file_index(_FRIEREN_FILES, "1") == 0
    assert _pick_batch_file_index(_FRIEREN_FILES, "7") == 6
    assert _pick_batch_file_index(_FRIEREN_FILES, "28") == 27


def test_pick_index_ignores_non_episode_files_and_order():
    files = [
        {"name": "[SubsPlease] Show (01-03) [Batch]/NCOP.mkv"},
        {"name": "[SubsPlease] Show - 03 (1080p).mkv"},
        {"name": "[SubsPlease] Show - 01 (1080p).mkv"},
    ]
    # Episode 3 is the second file even though it is not last.
    assert _pick_batch_file_index(files, "3") == 1
    assert _pick_batch_file_index(files, "1") == 2


def test_pick_index_none_when_missing_or_bad():
    assert _pick_batch_file_index(_FRIEREN_FILES, "29") is None
    assert _pick_batch_file_index(_FRIEREN_FILES, "abc") is None
    assert _pick_batch_file_index([], "1") is None


def test_xs_url_roundtrip():
    # As the nyaa provider builds it: fully URL-encoded.
    mag = (
        "magnet:?xt=urn:btih:" + "a" * 40
        + "&dn=x&xs=https%3A%2F%2Fnyaa.si%2Fdownload%2F123.torrent&x.aniep=7"
    )
    assert _xs_url(mag) == "https://nyaa.si/download/123.torrent"
    assert _xs_url("magnet:?xt=urn:btih:" + "a" * 40) is None
    # Non-http xs (e.g. a dht: hint) is ignored.
    assert _xs_url("magnet:?xt=urn:btih:" + "a" * 40 + "&xs=dht%3A%2F%2Fabc") is None


def test_magnet_info_hash():
    assert _magnet_info_hash("magnet:?xt=urn:btih:" + "AbC1" * 10) == "abc1" * 10
    assert _magnet_info_hash("https://example.com/x.torrent") is None


def test_stream_file_url_normalizes_and_encodes():
    # Windows metadata joins paths with backslash; the server route needs '/'
    # (verified live: the backslash form 404s).
    url = _stream_file_url(8150, "f" * 40, "Pack [Batch]\\Show - 07 (1080p).mkv")
    assert url == (
        "http://localhost:8150/webtorrent/" + "f" * 40
        + "/Pack%20%5BBatch%5D/Show%20-%2007%20%281080p%29.mkv"
    )


def test_valid_torrent_file(tmp_path):
    good = tmp_path / "good.torrent"
    good.write_bytes(b"d8:announce...")
    bad = tmp_path / "bad.torrent"
    bad.write_bytes(b"<html>blocked</html>")
    empty = tmp_path / "empty.torrent"
    empty.write_bytes(b"")
    assert _valid_torrent_file(good)
    assert not _valid_torrent_file(bad)
    assert not _valid_torrent_file(empty)
    assert not _valid_torrent_file(tmp_path / "missing.torrent")
