"""Tests for parsing mpv's playback position out of captured output.

This is what lets auto-next tell "watched to the end" from "quit early" in the
clean (non-IPC) playback path.
"""

from viu_media.libs.player.mpv.player import parse_playback_time


def test_takes_last_status_line_from_carriage_returns():
    # mpv rewrites the status line in place with \r; the last one is where
    # playback actually stopped.
    out = (
        "Playing: https://x/ep.m3u8\n"
        "AV: 00:00:01 / 00:23:00 (0%)\r"
        "AV: 00:11:30 / 00:23:00 (50%)\r"
        "AV: 00:22:45 / 00:23:00 (98%)\r"
    )
    assert parse_playback_time(out, "") == ("00:22:45", "00:23:00")


def test_reads_from_stderr_when_stdout_empty():
    err = "AV: 00:23:00 / 00:23:00 (100%)\r"
    assert parse_playback_time("", err) == ("00:23:00", "00:23:00")


def test_video_only_status_line():
    # Video-only streams print "V:" instead of "AV:".
    out = "V: 00:05:00 / 00:24:00 (20%)\r"
    assert parse_playback_time(out, None) == ("00:05:00", "00:24:00")


def test_no_status_line_returns_none():
    assert parse_playback_time("some log\nother log", "warnings") == (None, None)


def test_none_inputs():
    assert parse_playback_time(None, None) == (None, None)


def test_early_quit_reports_partial_position():
    out = "AV: 00:02:00 / 00:23:00 (8%)\r"
    stop, total = parse_playback_time(out, "")
    # A partial position -> the caller's reached_end check will be False.
    assert (stop, total) == ("00:02:00", "00:23:00")
