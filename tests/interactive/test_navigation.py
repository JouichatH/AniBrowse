"""Navigation integration tests: drive real menu flows via the session loop.

These lock in the navigation revision: Esc (an exhausted selector raising
NavigationAbort) always goes back one level, Back at the root exits, and no
menu is a dead end. They also exercise the full stream flow end to end
(main -> search -> results -> media_actions -> provider_search -> episodes ->
servers -> player_controls) with no fzf/mpv/network.
"""

import pytest

import viu_media.cli.interactive.menu.media._source_fallback as sf
from tests.conftest import drive, make_context, make_state
from tests.support.fakes import (
    FakeAnimeProvider,
    FakeApiClient,
    FakeFeedback,
    FakePlayerService,
    FakeSelector,
    FakeWatchHistory,
    make_anime,
    make_media_item,
    make_media_search_result,
    pick,
)
from viu_media.libs.media_api.params import MediaSearchParams


@pytest.fixture
def no_network_nyaa(monkeypatch):
    """Neutralise the nyaa fallback so no menu reaches the network."""
    monkeypatch.setattr(sf, "nyaa_extra_episodes", lambda *a, **k: [])
    monkeypatch.setattr(sf, "nyaa_servers", lambda *a, **k: [])


@pytest.fixture
def stream_config():
    """AppConfig wired for headless, deterministic driving (no preview/prompts)."""
    from viu_media.core.config import AppConfig

    cfg = AppConfig()
    cfg.general.icons = False
    cfg.general.preview = "none"  # no preview workers / subprocess
    cfg.general.auto_select_anime_result = True  # provider_search needs no prompt
    cfg.stream.continue_from_watch_history = False
    return cfg


def _media_ctx(config, selector, player=None, resume=(None, None)):
    """Context with a matched 3-episode media item + provider."""
    media = make_media_item(id=1, title="Test Anime", episodes=3)
    api = FakeApiClient(search_result=make_media_search_result(media))
    provider = FakeAnimeProvider(
        anime=make_anime(id="anime-1", title="Test Anime", episodes=["1", "2", "3"])
    )
    return (
        make_context(
            config=config,
            selector=selector,
            media_api=api,
            provider=provider,
            player=player or FakePlayerService(),
            feedback=FakeFeedback(),
            watch_history=FakeWatchHistory(resume=resume),
        ),
        media,
    )


def _results_state(media):
    return make_state(
        "results",
        media_api={
            "search_result": {media.id: media},
            "search_params": MediaSearchParams(query="test"),
        },
    )


# ---- full stream flow ----------------------------------------------------


def test_full_stream_flow_reaches_player_and_exits(stream_config, no_network_nyaa):
    # Script: pick the anime, choose "Stream", pick episode 1, then at the
    # post-playback menu pick "Main Menu"; the main menu's prompt then runs out
    # of script (Esc) and the loop unwinds to empty.
    selector = FakeSelector(
        [pick("Test Anime"), pick("Stream"), pick("1"), pick("Main Menu")]
    )
    player = FakePlayerService()
    ctx, media = _media_ctx(stream_config, selector, player)

    final = drive(ctx, [make_state("main"), _results_state(media)])

    # The player was actually launched for episode 1 - the flow is not a dead end.
    assert player.play_calls, "should have reached the player"
    params = player.play_calls[0][0]
    assert params.episode == "1"

    # "Main Menu" reset to root, then Esc quit; the loop terminated cleanly.
    assert final == []

    # It really traversed the menu chain (several selector prompts).
    prompts = [c[1] for c in selector.calls]
    assert any("Select Anime" in p for p in prompts)
    assert any("Episode" in p for p in prompts)


def test_auto_next_advances_through_episodes(stream_config, no_network_nyaa):
    """With auto_next + a fully-watched result, player_controls advances itself."""
    stream_config.stream.auto_next = True
    from viu_media.libs.player.types import PlayerResult

    # Every episode "reaches the end" (100%) -> auto-advance until the last.
    player = FakePlayerService(
        results=[
            PlayerResult(episode=str(n), stop_time="00:23:00", total_time="00:23:00")
            for n in range(1, 6)
        ]
    )
    # Episode 1 chosen manually; 2 and 3 arrive via auto-advance. At the final
    # (last-episode) menu pick "Main Menu", then Esc quits from root.
    selector = FakeSelector(
        [pick("Test Anime"), pick("Stream"), pick("1"), pick("Main Menu")]
    )
    ctx, media = _media_ctx(stream_config, selector, player)

    final = drive(ctx, [make_state("main"), _results_state(media)])

    # Played 1, 2, 3 by auto-advance (3 is the last; then the menu prompts).
    played = [c[0].episode for c in player.play_calls]
    assert played == ["1", "2", "3"]
    assert final == []


# ---- Esc backs out of every prompting menu (no dead ends) -----------------


def test_esc_backs_out_of_results(stream_config):
    selector = FakeSelector([])  # Esc immediately
    ctx, media = _media_ctx(stream_config, selector)
    final = drive(ctx, [make_state("main"), _results_state(media)])
    assert final == []


def test_esc_backs_out_of_episodes(stream_config, no_network_nyaa):
    selector = FakeSelector([])
    ctx, media = _media_ctx(stream_config, selector)
    provider_anime = make_anime(id="anime-1", title="Test Anime", episodes=["1", "2", "3"])
    episodes_state = make_state(
        "episodes",
        media_api={
            "search_result": {media.id: media},
            "media_id": media.id,
            "search_params": MediaSearchParams(query="test"),
        },
        provider={"anime": provider_anime},
    )
    final = drive(
        ctx, [make_state("main"), _results_state(media), episodes_state]
    )
    assert final == []


def test_esc_backs_out_of_player_controls(stream_config):
    selector = FakeSelector([])
    ctx, media = _media_ctx(stream_config, selector)
    provider_anime = make_anime(id="anime-1", title="Test Anime", episodes=["1", "2", "3"])
    from tests.support.fakes import make_server

    server = make_server(name="TOP", episode="1")
    pc_state = make_state(
        "player_controls",
        media_api={
            "search_result": {media.id: media},
            "media_id": media.id,
            "search_params": MediaSearchParams(query="test"),
        },
        provider={
            "anime": provider_anime,
            "episode": "1",
            "servers": {"TOP": server},
            "server_name": "TOP",
            "reached_end": False,
        },
    )
    final = drive(ctx, [make_state("main"), _results_state(media), pc_state])
    assert final == []


def test_back_at_root_exits(stream_config):
    """Esc at the main menu (root) empties the stack - the app quits."""
    selector = FakeSelector([])
    ctx, _ = _media_ctx(stream_config, selector)
    final = drive(ctx, make_state("main"))
    assert final == []
