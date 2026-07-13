"""Tests for parse_episode_range: slicing semantics + hardened clamping."""

import pytest

from viu_media.cli.utils.parser import parse_episode_range
from viu_media.core.exceptions import InvalidEpisodeRangeError

EPS = [str(n) for n in range(1, 11)]  # "1".."10"


def r(spec, eps=EPS):
    return list(parse_episode_range(spec, eps))


@pytest.mark.parametrize(
    "spec, expected",
    [
        (None, EPS),
        ("", EPS),
        (":", EPS),
        ("2:5", ["3", "4", "5"]),
        ("5:", ["6", "7", "8", "9", "10"]),
        (":3", ["1", "2", "3"]),
        ("2:8:2", ["3", "5", "7"]),
        ("5", ["6", "7", "8", "9", "10"]),
        ("0:0", []),
    ],
)
def test_documented_ranges(spec, expected):
    assert r(spec) == expected


def test_input_is_sorted_numerically_not_lexically():
    # "10" must not sort before "2"; the parser sorts by float first.
    assert r("0:3", ["10", "2", "1", "20"]) == ["1", "2", "10"]


def test_out_of_range_start_yields_empty_not_error():
    # Standard slice clamping: a start past the end is empty (not a crash).
    assert r("100:") == []


def test_end_beyond_length_clamps_to_all():
    assert r(":999") == EPS


@pytest.mark.parametrize("spec", ["-2:", ":-1", "-1", "-3:-1", "-1:5:2"])
def test_negative_indices_rejected(spec):
    # Negatives used to silently return tail episodes (Python wrap-around) -
    # a real footgun for the download callers. They must now be rejected.
    with pytest.raises(InvalidEpisodeRangeError):
        r(spec)


@pytest.mark.parametrize(
    "spec", ["a:b", "1.5", "x", "1:z", "5:6:0", "1:2:3:4", "::", "1::2", "1:2:"]
)
def test_invalid_specs_raise(spec):
    with pytest.raises((InvalidEpisodeRangeError, ValueError)):
        r(spec)


def test_zero_step_rejected():
    with pytest.raises(InvalidEpisodeRangeError):
        r("1:5:0")


def test_error_type_is_also_valueerror():
    # InvalidEpisodeRangeError subclasses ValueError for callers catching either.
    with pytest.raises(ValueError):
        r("-1")
