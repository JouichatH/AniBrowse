"""Regression tests for the IPC auto-next path.

The bug: a transient ``show-text`` timeout during the eof->idle transition was
unguarded, so it unwound all the way to ``_play_with_ipc``'s
``except MPVIPCError`` and collapsed the whole IPC player to the non-IPC
fallback - meaning "Fetching next episode..." never advanced. These tests
drive the player headlessly with a FakeIPCClient and assert that a failing
``show-text`` does NOT trigger the fallback and that auto-next still issues a
``loadfile`` for the next episode.
"""


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
        url="https://example.com/ep1.m3u8",
        title="Test Anime - Episode 1",
        query="test anime",
        episode=episode,
    )


def _play(client, provider, stream_config=None):
    base_player = FakeBasePlayer()
    player = MpvIPCPlayer(stream_config or _stream_config(), ipc_client=client)
    result = player.play(
        base_player,
        _params(),
        provider=provider,
        anime=provider.anime,
    )
    return player, base_player, result


def test_show_text_timeout_does_not_collapse_to_non_ipc(ipc_client_factory):
    """eof arrives, show-text times out - auto-next must still issue loadfile."""
    provider = FakeAnimeProvider(
        anime=make_anime(episodes=["1", "2", "3"]),
        servers={"2": [make_server(name="TOP", link="https://example.com/ep2.m3u8")]},
    )
    client = ipc_client_factory(
        events=[{"event": "end-file", "reason": "eof"}],
        fail_on={"show-text"},
        shutdown_when=lambda c: bool(c.commands_named("loadfile")),
    )

    player, base_player, _ = _play(client, provider)

    # The non-IPC fallback would have called the base player's play(); it must not.
    assert base_player.play_calls == [], "must not fall back to non-IPC playback"

    # Auto-next advanced to episode 2 and loaded its stream.
    loadfiles = client.commands_named("loadfile")
    assert loadfiles, "auto-next should have issued a loadfile for the next episode"
    assert loadfiles[-1][1] == "https://example.com/ep2.m3u8"
    assert player.player_state.episode == "2"


def test_eof_without_auto_next_does_not_advance(ipc_client_factory):
    provider = FakeAnimeProvider(anime=make_anime(episodes=["1", "2", "3"]))
    client = ipc_client_factory(
        events=[{"event": "end-file", "reason": "eof"}],
        shutdown_when=lambda c: c._idle_polls > 3,
    )
    _play(client, provider, stream_config=_stream_config(auto_next=False))

    assert client.commands_named("loadfile") == []


def test_non_eof_end_file_never_advances(ipc_client_factory):
    """A "stop"/"quit" end-file (reload, user exit) must not auto-advance."""
    provider = FakeAnimeProvider(anime=make_anime(episodes=["1", "2", "3"]))
    client = ipc_client_factory(
        events=[{"event": "end-file", "reason": "stop"}],
        shutdown_when=lambda c: c._idle_polls > 3,
    )
    _play(client, provider)

    assert client.commands_named("loadfile") == []


def test_auto_next_falls_back_to_nyaa_past_last_episode(
    ipc_client_factory, monkeypatch
):
    """Past the provider's last episode, auto-next uses the nyaa fallback."""
    provider = FakeAnimeProvider(
        anime=make_anime(episodes=["1"]),  # only episode 1 known to provider
        servers={},  # provider has no streams for anything
    )

    nyaa_calls = []

    def fake_nyaa_servers(query, episode, translation_type, quality):
        nyaa_calls.append((query, episode, translation_type, quality))
        return [make_server(name="TOP", link=f"magnet:ep{episode}")]

    monkeypatch.setattr(
        "viu_media.cli.interactive.menu.media._source_fallback.nyaa_servers",
        fake_nyaa_servers,
    )

    client = ipc_client_factory(
        events=[{"event": "end-file", "reason": "eof"}],
        shutdown_when=lambda c: bool(c.commands_named("loadfile")),
    )
    player, base_player, _ = _play(client, provider)

    assert base_player.play_calls == []
    assert nyaa_calls, "should have consulted the nyaa fallback for episode 2"
    assert nyaa_calls[-1][1] == "2"
    loadfiles = client.commands_named("loadfile")
    assert loadfiles and loadfiles[-1][1] == "magnet:ep2"
    assert player.player_state.episode == "2"
