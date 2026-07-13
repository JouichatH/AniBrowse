"""Tests for formatter.sanitize_cache_key - the preview injection guard."""

import pytest

from viu_media.core.utils import formatter


@pytest.mark.parametrize(
    "raw",
    [
        'Naruto"""\nimport os; os.system("rm -rf /")\n"""',  # triple-quote breakout
        r"Show ending in a backslash\\",
        "Title with {SCALE_UP} placeholder",
        'has "double" and \'single\' quotes',
        "line1\nline2\r\ttab",
    ],
)
def test_result_cannot_break_out_of_triple_quoted_literal(raw):
    key = formatter.sanitize_cache_key(raw)
    # No character that could terminate/redirect a """...""" literal or
    # re-trigger {...} placeholder substitution survives.
    for bad in ('"', "\\", "\n", "\r", "\t", "{", "}", "'"):
        assert bad not in key
    # And the sanitized value embeds harmlessly and evaluates back to itself.
    literal = f'"""{key}"""'
    assert eval(literal) == key  # noqa: S307 - trusted, sanitized input under test


def test_stable_and_lossless_for_plain_titles():
    assert formatter.sanitize_cache_key("Spy x Family") == "Spy x Family"
    assert formatter.sanitize_cache_key("Mushoku Tensei S3") == "Mushoku Tensei S3"


def test_empty_and_none():
    assert formatter.sanitize_cache_key("") == ""
    assert formatter.sanitize_cache_key(None) == ""


def test_deterministic():
    t = 'weird\\"title{x}'
    assert formatter.sanitize_cache_key(t) == formatter.sanitize_cache_key(t)
