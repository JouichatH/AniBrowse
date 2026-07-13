"""Tests for the menu-path episode prefetch cache."""

import viu_media.cli.interactive.menu.media._prefetch as pf
from tests.support.fakes import FakeAnimeProvider, make_anime, make_server
from viu_media.core.config import AppConfig


def _config():
    return AppConfig()


def test_neighbour_episodes():
    anime = make_anime(episodes=["1", "2", "3"])
    assert set(pf.neighbour_episodes(anime, "sub", "2")) == {"1", "3"}
    assert pf.neighbour_episodes(anime, "sub", "1") == ["2"]
    # Past the provider's last -> numeric next, plus previous.
    assert pf.neighbour_episodes(anime, "sub", "3") == ["4", "2"]


def test_resolve_servers_uses_provider_then_nyaa(monkeypatch):
    provider = FakeAnimeProvider(
        servers={"2": [make_server(name="Luf-mp4", link="u2")]}
    )
    servers = pf.resolve_servers(provider, _config(), "anime-1", "Show", "2")
    assert [s.link for s in (s.links[0] for s in servers)] == ["u2"]

    # Missing on provider -> nyaa fallback.
    nyaa = [make_server(name="nyaa:SubsPlease (5)", link="magnet:x")]
    monkeypatch.setattr(pf, "nyaa_servers", lambda *a, **k: nyaa, raising=False)
    import viu_media.cli.interactive.menu.media._source_fallback as sf

    monkeypatch.setattr(sf, "nyaa_servers", lambda *a, **k: nyaa)
    empty_provider = FakeAnimeProvider(servers={})
    got = pf.resolve_servers(empty_provider, _config(), "anime-1", "Show", "9")
    assert got == nyaa


def test_get_servers_consumes_prefetched_cache():
    provider = FakeAnimeProvider(
        servers={"2": [make_server(name="Luf-mp4", link="LIVE")]}
    )
    cfg = _config()
    # Seed the cache as if a prefetch worker finished for episode 2.
    cached = [make_server(name="Luf-mp4", link="CACHED")]
    key = pf._key("anime-1", "2", cfg.stream.translation_type)
    pf._CACHE[key] = cached
    provider.calls.clear()

    got = pf.get_servers(provider, cfg, "anime-1", "Show", "2")

    assert got == cached  # served from cache
    assert provider.calls == []  # provider was not queried
    # The entry was consumed (one-shot).
    assert key not in pf._CACHE


def test_prefetch_neighbours_populates_cache():
    provider = FakeAnimeProvider(
        anime=make_anime(id="anime-1", episodes=["1", "2", "3"]),
        servers={
            "1": [make_server(name="Luf-mp4", link="u1")],
            "3": [make_server(name="Luf-mp4", link="u3")],
        },
    )
    cfg = _config()
    pf.prefetch_neighbours(provider, cfg, provider.anime, "Show", "2")

    # Wait for the daemon workers to finish (fakes are fast).
    import time

    for _ in range(200):
        with pf._LOCK:
            done = not pf._INFLIGHT
        if done:
            break
        time.sleep(0.01)

    tt = cfg.stream.translation_type
    assert pf._key("anime-1", "1", tt) in pf._CACHE
    assert pf._key("anime-1", "3", tt) in pf._CACHE
