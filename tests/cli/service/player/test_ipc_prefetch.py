"""Tests for in-player episode prefetching (instant next/prev)."""

from tests.support.fakes import (
    FakeAnimeProvider,
    FakeBasePlayer,
    make_anime,
    make_server,
)
from viu_media.core.config import AppConfig
from viu_media.cli.service.player.ipc.mpv import MpvIPCPlayer
from viu_media.libs.player.params import PlayerParams


def _stream_config(**overrides):
    cfg = AppConfig().stream
    cfg.auto_next = True
    cfg.opening_skip = False
    cfg.ending_skip = False
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _params(episode="1"):
    return PlayerParams(
        url="https://cdn/ep1.m3u8",
        title="Test Anime - Episode 1",
        query="test anime",
        episode=episode,
    )


def _play(client, provider, episode="1"):
    base_player = FakeBasePlayer()
    player = MpvIPCPlayer(_stream_config(), ipc_client=client)
    player.play(
        base_player, _params(episode), provider=provider, anime=provider.anime
    )
    return player


def test_file_loaded_prefetches_neighbours(ipc_client_factory):
    provider = FakeAnimeProvider(
        anime=make_anime(episodes=["1", "2", "3"]),
        servers={
            "2": [make_server(name="Luf-mp4", link="https://cdn/ep2.m3u8")],
            "3": [make_server(name="Luf-mp4", link="https://cdn/ep3.m3u8")],
        },
    )
    # Start on episode 2 so BOTH neighbours (1 and 3) exist to prefetch.
    client = ipc_client_factory(
        events=[{"event": "file-loaded"}],
        shutdown_when=lambda c: c._idle_polls > 3,
    )
    assert provider.servers is not None
    provider.servers["1"] = [make_server(name="Luf-mp4", link="https://cdn/ep1.m3u8")]
    player = _play(client, provider, episode="2")

    for t in player._prefetch_threads:
        t.join(timeout=3)

    # Both the next (3) and previous (1) episodes were prefetched.
    assert set(player._prefetch) == {"1", "3"}


def test_fetch_uses_prefetch_cache_without_hitting_provider(ipc_client_factory):
    provider = FakeAnimeProvider(
        anime=make_anime(episodes=["1", "2", "3"]),
        servers={"2": [make_server(name="Luf-mp4", link="https://cdn/ep2.m3u8")]},
    )
    client = ipc_client_factory(
        events=[{"event": "end-file", "reason": "eof"}],
        shutdown_when=lambda c: bool(c.commands_named("loadfile")),
    )
    base_player = FakeBasePlayer()
    player = MpvIPCPlayer(_stream_config(), ipc_client=client)

    # Pre-seed the cache for episode 2 (as if prefetch already finished), then
    # forget every provider call so we can prove the fetch used the cache.
    cached = {"Luf-mp4": make_server(name="Luf-mp4", link="https://cdn/CACHED.m3u8")}
    player._prefetch["2"] = cached
    provider.calls.clear()

    player.play(
        base_player, _params("1"), provider=provider, anime=provider.anime
    )

    # Auto-next loaded the CACHED url, and never queried the provider for ep 2.
    loadfiles = client.commands_named("loadfile")
    assert loadfiles and loadfiles[-1][1] == "https://cdn/CACHED.m3u8"
    ep2_calls = [
        c for c in provider.calls
        if c[0] == "episode_streams" and c[1].episode == "2"
    ]
    assert ep2_calls == [], "fetch should have used the prefetch cache, not the network"


def test_neighbour_episodes_computation(ipc_client_factory):
    provider = FakeAnimeProvider(anime=make_anime(episodes=["1", "2", "3"]))
    player = MpvIPCPlayer(_stream_config(), ipc_client=ipc_client_factory())
    player.anime = provider.anime
    player.provider = provider
    from viu_media.cli.service.player.ipc.mpv import PlayerState

    player.player_state = PlayerState(_stream_config(), "q", "2")
    assert set(player._neighbour_episodes()) == {"1", "3"}

    # First episode: only a next neighbour.
    player.player_state = PlayerState(_stream_config(), "q", "1")
    assert player._neighbour_episodes() == ["2"]

    # Past the provider's last: numeric next only.
    player.player_state = PlayerState(_stream_config(), "q", "3")
    assert player._neighbour_episodes() == ["4", "2"]
