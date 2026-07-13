"""Tests for the servers menu's source-display + neighbour helpers."""

from types import SimpleNamespace

from viu_media.cli.interactive.menu.media.servers import (
    _neighbour_episode,
    _source_summary,
    _stream_host,
)
from viu_media.core.config import AppConfig
from tests.support.fakes import make_anime, make_server


def test_stream_host():
    assert _stream_host("https://a4.mp4upload.com:183/d/abc") == "a4.mp4upload.com"
    assert _stream_host("magnet:?xt=urn:btih:deadbeef") == "torrent/webtorrent"
    assert _stream_host("https://x.torrent".replace("x", "host/file.torrent")) == (
        "torrent/webtorrent"
    )


def test_source_summary_provider_and_nyaa():
    ctx = SimpleNamespace(config=AppConfig())
    prov = _source_summary(ctx, make_server(name="Luf-mp4"), "https://cdn.example/x.m3u8")
    assert "allanime" in prov and "Luf-mp4" in prov and "cdn.example" in prov
    assert "1080p" in prov and "sub" in prov

    nyaa = _source_summary(
        ctx, make_server(name="nyaa:SubsPlease (5)"), "magnet:?xt=urn:btih:ab"
    )
    assert "nyaa (torrent)" in nyaa and "torrent/webtorrent" in nyaa


def test_neighbour_episode():
    anime = make_anime(episodes=["1", "2", "3"])
    assert _neighbour_episode(anime, "sub", "2", "next") == "3"
    assert _neighbour_episode(anime, "sub", "2", "previous") == "1"
    assert _neighbour_episode(anime, "sub", "1", "previous") is None
    # Past the last: numeric next (nyaa fallback then serves it).
    assert _neighbour_episode(anime, "sub", "3", "next") == "4"
    # Non-numeric episode past the list: no numeric next.
    assert _neighbour_episode(anime, "sub", "Special", "next") is None
