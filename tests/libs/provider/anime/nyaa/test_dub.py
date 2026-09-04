"""Honouring the configured audio track.

Torrent releases are frequently dual-audio: one file carries both Japanese and
English. nyaa used to hardcode every stream as "sub" and advertise no dub
episodes at all, so a user configured for dub had to switch the audio track by
hand every single episode.
"""

from viu_media.libs.provider.anime.nyaa.provider import (
    _DUAL_AUDIO_RE,
    _ENGLISH_DUB_RE,
    Nyaa,
)


def test_dual_audio_and_dub_releases_are_recognised():
    dual = "[ToonsHub] Solo Leveling S02E13 1080p CR WEB-DL MULTi AAC2.0"
    assert _DUAL_AUDIO_RE.search(dual)
    assert _DUAL_AUDIO_RE.search("[AUTISM] Frieren - S01v2 (BD Remux) Dual Audio")
    assert _ENGLISH_DUB_RE.search("[Yameii] Jujutsu Kaisen - S03E12 [English Dub]")
    # A plain simulcast is sub-only and must not be offered as a dub.
    assert not _DUAL_AUDIO_RE.search("[SubsPlease] Sousou no Frieren (01-28) (1080p)")


def test_only_english_capable_releases_count_as_dub():
    items = [
        {"title": "a", "dual_audio": True, "dub_only": False},
        {"title": "b", "dual_audio": False, "dub_only": True},
        {"title": "c", "dual_audio": False, "dub_only": False},
    ]
    assert [i["title"] for i in Nyaa._dub_items(items)] == ["a", "b"]


def test_dub_magnet_carries_the_season_marker():
    magnet = Nyaa._magnet("abc", "Pack", select_ep="2", select_season=2)
    assert "x.aniep=2" in magnet
    assert "x.anisn=2" in magnet


def test_no_season_marker_on_a_single_episode_torrent():
    magnet = Nyaa._magnet("abc", "Ep", select_ep=None, select_season=None)
    assert "x.aniep" not in magnet and "x.anisn" not in magnet
