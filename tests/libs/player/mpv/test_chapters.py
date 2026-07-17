"""Tests for capturing mpv's embedded chapter list out of captured output."""

from viu_media.libs.player.mpv.player import parse_mpv_chapters


def test_parses_chapter_lines():
    out = (
        "[ani-chapters] count=4\n"
        "[ani-chapters] #1 t=0.000 title=Intro\n"
        "[ani-chapters] #2 t=90.000 title=Opening\n"
        "[ani-chapters] #3 t=1300.500 title=Ending\n"
        "[ani-chapters] #4 t=1380.000 title=Preview\n"
    )
    assert parse_mpv_chapters(out, "") == [
        (0.0, "Intro"),
        (90.0, "Opening"),
        (1300.5, "Ending"),
        (1380.0, "Preview"),
    ]


def test_reads_from_stderr_too():
    err = "[ani-chapters] #1 t=12.000 title=OP"
    assert parse_mpv_chapters("", err) == [(12.0, "OP")]


def test_titles_with_spaces_and_symbols():
    out = "[ani-chapters] #1 t=5.000 title=Part A / cold open"
    assert parse_mpv_chapters(out, None) == [(5.0, "Part A / cold open")]


def test_no_chapters():
    assert parse_mpv_chapters("regular mpv log\nAV: 00:01 / 24:00 (0%)", "") == []


def test_none_inputs():
    assert parse_mpv_chapters(None, None) == []
