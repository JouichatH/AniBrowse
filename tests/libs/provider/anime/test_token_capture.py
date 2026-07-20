"""Tests for the browser token-capture helper (pure logic - no real browser).

The Playwright drive itself is exercised live during development; here we pin
the parts that must stay correct without a network or a browser: parsing the
captured request, cache freshness, and the opt-in gate that keeps a browser
from ever popping up for a user who never asked for it.
"""

import json
import time

import pytest

from viu_media.libs.provider.anime import token_capture as tc


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Point the token cache at a temp file so tests never touch real state."""
    cache = tmp_path / "allanime_token.json"
    monkeypatch.setattr(tc, "_cache_file", lambda: cache)
    return cache


def _source_url(host="https://api.mkissa.net/api", token="TOK", qh="deadbeef"):
    from urllib.parse import quote

    ext = json.dumps(
        {"persistedQuery": {"version": 1, "sha256Hash": qh}, "aaReq": token},
        separators=(",", ":"),
    )
    variables = json.dumps({"showId": "X", "episodeString": "1"}, separators=(",", ":"))
    return f"{host}?variables={quote(variables)}&extensions={quote(ext)}"


def test_parse_source_request_reads_token_host_and_frontend_referer():
    url = _source_url()
    parsed = tc._parse_source_request(
        url, headers={"Referer": "https://mkissa.to/", "Origin": "https://mkissa.to"}
    )
    assert parsed["token"] == "TOK"
    assert parsed["query_hash"] == "deadbeef"
    assert parsed["api_host"] == "https://api.mkissa.net/api"
    # Referer/Origin come from the request headers (frontend), NOT the api host.
    assert parsed["referer"] == "https://mkissa.to/"
    assert parsed["origin"] == "https://mkissa.to"


def test_parse_source_request_falls_back_to_frontend_when_no_referer_header():
    parsed = tc._parse_source_request(_source_url(), headers={})
    # Derived from the api host by stripping the leading 'api.' - never the api host itself.
    assert parsed["referer"] == "https://mkissa.net/"


def test_parse_source_request_ignores_non_source_requests():
    # A URL with no aaReq extension is not a token request.
    assert tc._parse_source_request("https://api.mkissa.net/api?variables=%7B%7D") is None


def test_load_cached_token_respects_freshness(_isolated_cache):
    payload = {
        "token": "T",
        "query_hash": "H",
        "api_host": "https://api.mkissa.net/api",
        "captured_at": time.time(),
    }
    _isolated_cache.write_text(json.dumps(payload), encoding="utf-8")
    assert tc.load_cached_token()["token"] == "T"

    # Too old -> None.
    payload["captured_at"] = time.time() - (tc.DEFAULT_MAX_AGE + 10)
    _isolated_cache.write_text(json.dumps(payload), encoding="utf-8")
    assert tc.load_cached_token() is None


def test_load_cached_token_rejects_incomplete(_isolated_cache):
    _isolated_cache.write_text(
        json.dumps({"token": "T", "captured_at": time.time()}), encoding="utf-8"
    )
    assert tc.load_cached_token() is None  # missing query_hash / api_host


def test_invalidate_removes_cache(_isolated_cache):
    _isolated_cache.write_text("{}", encoding="utf-8")
    tc.invalidate_cached_token()
    assert not _isolated_cache.exists()


def test_get_active_token_never_launches_browser_for_new_user(_isolated_cache, monkeypatch):
    # No cache file ever existed -> not opted in -> must NOT capture.
    called = {"n": 0}
    monkeypatch.setattr(tc, "capture_token", lambda **k: called.__setitem__("n", called["n"] + 1))
    monkeypatch.setattr(tc, "playwright_available", lambda: True)
    assert tc.get_active_token() is None
    assert called["n"] == 0


def test_get_active_token_refreshes_for_opted_in_user(_isolated_cache, monkeypatch):
    # A stale cache file exists (user captured before) -> silent refresh allowed.
    _isolated_cache.write_text(
        json.dumps({"token": "old", "captured_at": 0}), encoding="utf-8"
    )
    fresh = {"token": "new", "query_hash": "H", "api_host": "h", "captured_at": time.time()}
    monkeypatch.setattr(tc, "capture_token", lambda **k: fresh)
    monkeypatch.setattr(tc, "playwright_available", lambda: True)
    assert tc.get_active_token() == fresh


def test_get_active_token_returns_fresh_cache_without_capture(_isolated_cache, monkeypatch):
    payload = {
        "token": "cached",
        "query_hash": "H",
        "api_host": "https://api.mkissa.net/api",
        "captured_at": time.time(),
    }
    _isolated_cache.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        tc, "capture_token", lambda **k: pytest.fail("should not capture with fresh cache")
    )
    assert tc.get_active_token()["token"] == "cached"
