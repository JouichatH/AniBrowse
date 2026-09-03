"""Episode-number parsing shared by the nyaa provider and the player."""

from viu_media.core.utils.episodes import episode_from_filename, is_extra_file


def test_scene_and_fansub_naming():
    assert episode_from_filename("Attack.on.Titan.2013.S04E01.1080p.AV1.mkv") == "1"
    assert episode_from_filename("[SubsPlease] Frieren - 03 (1080p) [ABC].mkv") == "3"
    assert episode_from_filename("[EMBER] Solo Leveling S01E13 [BDRip].mkv") == "13"
    assert episode_from_filename("Show_12_[Group].mkv") == "12"
    assert episode_from_filename("Show EP08.mkv") == "8"


def test_half_episodes_and_long_running_shows():
    assert episode_from_filename("[Grp] Show - 07.5 (OVA).mkv") == "7.5"
    assert episode_from_filename("[Grp] One Piece - 1176 (1080p).mkv") == "1176"


def test_refuses_to_guess():
    # A bare number could be a year or a resolution; guessing plays the wrong
    # file, which is worse than reporting nothing.
    assert episode_from_filename("Some Movie 1080p.mkv") is None
    assert episode_from_filename("") is None


def test_bundled_extras_are_recognised():
    # A complete collection carries a spin-off that reuses episode numbers.
    assert is_extra_file("[Anime Time] Attack on Titan Junior High - 01.mkv")
    assert is_extra_file("Show - OVA 01.mkv")
    assert is_extra_file("Show Movie 05.mkv")
    assert not is_extra_file("[Anime Time] Attack on Titan - 25.mkv")
