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


def test_multi_season_pack_picks_the_requested_season():
    """A "Season 1 + 2" pack holds S01E02 AND S02E02 - both "episode 2"."""
    from viu_media.core.utils.episodes import main_series_files

    names = [
        "S01E01-Im Used to It.mkv",
        "S01E02-If I Had One More Chance.mkv",
        "S02E01-Arise.mkv",
        "S02E02-Next Target.mkv",
    ]
    assert main_series_files(names, 1) == [
        "S01E01-Im Used to It.mkv",
        "S01E02-If I Had One More Chance.mkv",
    ]
    assert main_series_files(names, 2) == [
        "S02E01-Arise.mkv",
        "S02E02-Next Target.mkv",
    ]


def test_a_pack_without_the_requested_season_yields_nothing():
    from viu_media.core.utils.episodes import main_series_files

    assert main_series_files(["S01E01-One.mkv", "S01E02-Two.mkv"], 3) == []


def test_bundled_arc_does_not_hijack_episode_one():
    """The bug users hit: episode 1 played a side arc because it sorted first.

    A Demon Slayer collection carries "... Kimetsu no Yaiba - 01" and
    "... Mugen Train Arc - 01"; neither declares a season, so the main run is
    identified as the largest group of same-named files.
    """
    from viu_media.core.utils.episodes import main_series_files

    names = [
        "[AT] Demon Slayer - Kimetsu no Yaiba Mugen Train Arc - 01.mkv",
        "[AT] Demon Slayer - Kimetsu no Yaiba - 01.mkv",
        "[AT] Demon Slayer - Kimetsu no Yaiba - 02.mkv",
        "[AT] Demon Slayer - Kimetsu no Yaiba - 03.mkv",
    ]
    chosen = main_series_files(names, 1)
    assert "[AT] Demon Slayer - Kimetsu no Yaiba - 01.mkv" in chosen
    assert all("Mugen Train" not in n for n in chosen)


def test_series_key_ignores_group_tags_and_numbering():
    from viu_media.core.utils.episodes import series_key

    assert series_key("[Grp] Show Name - 01 [1080p][ABC123].mkv") == series_key(
        "[Other] Show Name - 24 (720p).mkv"
    )


def test_episode_titled_files_are_not_grouped_away():
    """A pack naming files by episode title must survive intact.

    Bleach's collection is "Bleach - 001 - The Day I Became A Shinigami.mkv",
    so every file has a unique name. Treating that as "many series" and keeping
    only the largest group cut 366 episodes down to 9. Numbers do not collide
    here, so there is nothing to disambiguate.
    """
    from viu_media.core.utils.episodes import main_series_files

    names = [
        "Bleach - 001 - The Day I Became A Shinigami.mkv",
        "Bleach - 002 - A Shinigamis Work.mkv",
        "Bleach - 003 - The Older Brothers Wish.mkv",
    ]
    assert main_series_files(names, 1) == names


def test_collisions_are_what_trigger_disambiguation():
    """Grouping kicks in only when two files claim the same episode."""
    from viu_media.core.utils.episodes import main_series_files

    names = [
        "Show - 01 - Some Title.mkv",
        "Show - 02 - Another Title.mkv",
        "Show Side Story - 01 - Extra.mkv",
    ]
    chosen = main_series_files(names, 1)
    assert all("Side Story" not in n for n in chosen)
    assert len(chosen) == 2
