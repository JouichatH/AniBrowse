"""Reading a season pack's episode list out of its .torrent file.

Completed shows reach nyaa mostly as packs whose title hides the episode range
("Complete Collection", "S01", "Batch"). Before this, the provider built an
EMPTY menu from 75 perfectly good results.
"""

from pathlib import Path

from viu_media.libs.provider.anime.nyaa.torrent import (
    torrent_episodes,
    torrent_file_names,
)

FIXTURE = Path(__file__).parent / "pack_fixture.bin"


def test_reads_file_names_from_a_real_bencoded_torrent():
    names = torrent_file_names(FIXTURE.read_bytes())
    assert "[Anime Time] Attack on Titan - 01.mkv" in names
    assert len(names) == 5


def test_episodes_skip_non_video_and_bundled_spinoffs():
    # readme.nfo is not video; "Junior High - 01" is a spin-off that reuses
    # episode 1 and must not be counted as the show's own episode.
    assert torrent_episodes(FIXTURE.read_bytes()) == ["1", "2"]


def test_malformed_input_is_not_fatal():
    assert torrent_file_names(b"") == []
    assert torrent_file_names(b"not a torrent") == []
    assert torrent_episodes(b"d") == []
