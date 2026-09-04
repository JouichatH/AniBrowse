"""mpv must start on the audio track the user configured."""

from viu_media.core.config import AppConfig
from viu_media.libs.player.mpv.player import MpvPlayer
from viu_media.libs.player.params import PlayerParams


def _args(translation_type):
    player = MpvPlayer(AppConfig().mpv)
    return player._create_mpv_cli_options(
        PlayerParams(
            url="x", title="T", query="q", episode="1",
            translation_type=translation_type,
        )
    )


def test_dub_starts_on_the_english_track():
    args = _args("dub")
    assert any(a.startswith("--alang=eng") for a in args)
    # No forced subtitle language: the sub track stays switchable in mpv.
    assert not any(a.startswith("--alang=jpn") for a in args)


def test_sub_starts_on_japanese_audio_with_english_subtitles():
    args = _args("sub")
    assert any(a.startswith("--alang=jpn") for a in args)
    assert any(a.startswith("--slang=eng") for a in args)


def test_nothing_is_forced_when_unset():
    assert not any("alang" in a for a in _args(None))
