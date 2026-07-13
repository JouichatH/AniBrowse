"""Tests for the pure helpers of scripts/dump_chapters.py."""

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "dump_chapters",
    Path(__file__).resolve().parents[2] / "scripts" / "dump_chapters.py",
)
dc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(dc)  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "spec, expected",
    [
        ("1-3", ["1", "2", "3"]),
        ("1,3,5", ["1", "3", "5"]),
        ("1-2,5,7-8", ["1", "2", "5", "7", "8"]),
        ("4", ["4"]),
    ],
)
def test_parse_episode_arg(spec, expected):
    assert dc.parse_episode_arg(spec) == expected


def test_parse_ffprobe_chapters():
    payload = """
    {"chapters": [
      {"start_time": "0.000000", "end_time": "90.000000", "tags": {"title": "Opening"}},
      {"start_time": "1300.0", "end_time": "1380.0", "tags": {"title": "Ending"}},
      {"start_time": "1380.0", "end_time": "1440.0"}
    ]}
    """
    assert dc.parse_ffprobe_chapters(payload) == [
        (0.0, 90.0, "Opening"),
        (1300.0, 1380.0, "Ending"),
        (1380.0, 1440.0, ""),
    ]


def test_parse_ffprobe_chapters_empty_or_bad():
    assert dc.parse_ffprobe_chapters("") == []
    assert dc.parse_ffprobe_chapters("not json") == []
    assert dc.parse_ffprobe_chapters('{"chapters": []}') == []


@pytest.mark.parametrize(
    "title, kind",
    [
        ("Opening", "op"),
        ("OP", "op"),
        ("NCOP", "op"),
        ("Intro", "op"),
        ("Ending", "ed"),
        ("ED", "ed"),
        ("Credits", "ed"),
        ("Outro", "ed"),
        ("Episode", None),
        ("Part A", None),
        ("Preview", None),
        ("Chapter 01", None),
        ("", None),
    ],
)
def test_classify_title(title, kind):
    assert dc.classify_title(title) == kind


def test_summarize_counts_and_classifies():
    rows = [
        ("1", 0.0, 90.0, "Opening"),
        ("2", 0.0, 90.0, "Opening"),
        ("1", 1300.0, 1380.0, "Ending"),
        ("2", 0.0, 60.0, "Episode"),
    ]
    summary = dc.summarize(rows)
    assert summary[0] == ("Opening", 2, "op")
    assert ("Ending", 1, "ed") in summary
    assert ("Episode", 1, None) in summary
