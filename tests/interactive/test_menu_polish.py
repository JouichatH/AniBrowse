"""Tests for the menu-polish round: cursor memory, local-first lists,
favorites, persisted toggles, download ranges, and the change-server override.
"""

import pytest

from tests.conftest import make_context
from tests.support.fakes import (
    FakeFeedback,
    FakeSelector,
)
from viu_media.cli.interactive.menu.media._cursor import remembered_choose
from viu_media.cli.interactive.menu.media.download_episodes import (
    _episodes_from_ranges,
)
from viu_media.cli.interactive.session import Switch
from viu_media.core.config import AppConfig


# ---- cursor memory -------------------------------------------------------


def test_remembered_choose_restores_last_index():
    sel = FakeSelector(["b", "c"])
    choices = ["a", "b", "c"]
    assert remembered_choose(sel, "menu-x", "p", choices) == "b"
    # Second entry of the same menu starts on the previously-picked row.
    remembered_choose(sel, "menu-x", "p", choices)
    assert sel.start_indices == [None, 1]


def test_remembered_choose_survives_label_churn_but_not_shrink():
    sel = FakeSelector([2, 0])
    # Toggle labels change text but keep position: index memory still applies.
    remembered_choose(sel, "m", "p", ["x (Current: True)", "y", "z"])
    remembered_choose(sel, "m", "p", ["x (Current: False)", "y"])  # list shrank
    # Remembered index 2 is out of range for the shrunk list -> no start_index.
    assert sel.start_indices == [None, None]


# ---- download episode ranges ---------------------------------------------

EPS = [str(i) for i in range(1, 51)]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1-24", [str(i) for i in range(1, 25)]),
        ("8", ["8"]),
        ("3,5-7", ["3", "5", "6", "7"]),
        ("48-", ["48", "49", "50"]),
        ("-3", ["1", "2", "3"]),
        ("1-50", EPS),
        ("", []),
        (None, []),
        ("abc", []),
        ("60-70", []),  # out of range -> nothing (caller warns)
    ],
)
def test_episodes_from_ranges(text, expected):
    assert _episodes_from_ranges(text, EPS) == expected


def test_episodes_from_ranges_respects_decimal_specials():
    assert _episodes_from_ranges("5-7", ["5", "5.5", "6", "7", "8"]) == [
        "5",
        "5.5",
        "6",
        "7",
    ]


# ---- switch: one-shot forced server --------------------------------------


def test_switch_forced_server_is_one_shot():
    sw = Switch()
    assert sw.forced_server is None
    sw.force_server("Luf-mp4")
    assert sw.forced_server == "Luf-mp4"
    assert sw.forced_server is None  # consumed


# ---- registry: favorites + status-flip regression ------------------------


@pytest.fixture
def registry(tmp_path):
    from viu_media.cli.service.registry.service import MediaRegistryService

    cfg = AppConfig()
    cfg.media_registry.media_dir = tmp_path / "media"
    cfg.media_registry.index_dir = tmp_path / "index"
    return MediaRegistryService("anilist", cfg.media_registry)


def test_favorite_toggle_roundtrip(registry):
    from tests.support.fakes import make_media_item

    media = make_media_item(id=77, title="Fav Show", episodes=12)
    assert registry.is_favorite(77) is False
    registry.update_media_index_entry(media_id=77, media_item=media, favorite=True)
    assert registry.is_favorite(77) is True
    favs = registry.get_favorites()
    assert [m.id for m in favs.media] == [77]
    registry.update_media_index_entry(media_id=77, media_item=media, favorite=False)
    assert registry.is_favorite(77) is False
    assert registry.get_favorites().media == []


def test_metadata_update_does_not_flip_completed_to_repeating(registry):
    """Regression: scoring/favoriting a COMPLETED show used to silently flip
    its status to REPEATING via the watch-update fallback."""
    from tests.support.fakes import make_media_item
    from viu_media.libs.media_api.types import UserMediaListStatus

    media = make_media_item(id=5, title="Done Show", episodes=12)
    registry.update_media_index_entry(
        media_id=5, media_item=media, status=UserMediaListStatus.COMPLETED
    )
    registry.update_media_index_entry(media_id=5, media_item=media, score=9.5)
    registry.update_media_index_entry(media_id=5, media_item=media, favorite=True)
    entry = registry.get_media_index_entry(5)
    assert entry is not None
    assert entry.status == UserMediaListStatus.COMPLETED


# ---- toggles persist to config.toml (against a tmp file) ------------------


def test_apply_toggle_flips_and_persists(tmp_path, monkeypatch):
    import viu_media.core.constants as constants
    from viu_media.cli.config.generate import generate_config_toml_from_app_model
    from viu_media.cli.interactive.menu.media import _toggles

    # Re-enable real persistence (the autouse fixture stubs it) at a tmp path.
    monkeypatch.setattr(
        _toggles, "_persist_field", getattr(_toggles._persist_field, "__wrapped__")
    )
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(
        generate_config_toml_from_app_model(AppConfig()), encoding="utf-8"
    )
    monkeypatch.setattr(constants, "USER_CONFIG", cfg_path)

    ctx = make_context(config=AppConfig(), feedback=FakeFeedback())
    before = ctx.config.stream.opening_skip
    _toggles.apply_toggle(ctx, "OPENING_SKIP")
    assert ctx.config.stream.opening_skip is (not before)

    # The on-disk config carries ONLY that change.
    from viu_media.cli.config.loader import ConfigLoader

    disk = ConfigLoader(config_path=cfg_path).load(allow_setup=False)
    assert disk.stream.opening_skip is (not before)
    assert disk.stream.quality == AppConfig().stream.quality  # untouched


def test_apply_toggle_translation_type_cycles():
    ctx = make_context(config=AppConfig(), feedback=FakeFeedback())
    from viu_media.cli.interactive.menu.media import _toggles

    start = ctx.config.stream.translation_type
    _toggles.apply_toggle(ctx, "TRANSLATION_TYPE")
    assert ctx.config.stream.translation_type != start
    _toggles.apply_toggle(ctx, "TRANSLATION_TYPE")
    assert ctx.config.stream.translation_type == start


# ---- drive-level: menus in the real loop ---------------------------------


from tests.conftest import drive, make_state  # noqa: E402
from tests.support.fakes import (  # noqa: E402
    FakeAnimeProvider,
    FakeApiClient,
    FakePlayerService,
    FakeWatchHistory,
    make_anime,
    make_media_item,
    make_media_search_result,
    pick,
)


@pytest.fixture
def polish_config():
    cfg = AppConfig()
    cfg.general.icons = False
    cfg.general.preview = "none"
    cfg.general.auto_select_anime_result = True
    cfg.stream.continue_from_watch_history = False
    return cfg


def _actions_state(media):
    return make_state(
        "media_actions",
        media_api={"search_result": {media.id: media}, "media_id": media.id},
    )


def test_media_actions_toggle_keeps_cursor(polish_config, registry):
    """Flipping a toggle re-renders the menu with the cursor ON that toggle
    (the reported bug: it snapped back to the top)."""
    media = make_media_item(id=1, title="Test Anime", episodes=3)
    sel = FakeSelector([pick("Toggle Opening Skip")])
    ctx = make_context(
        config=polish_config,
        selector=sel,
        media_api=FakeApiClient(search_result=make_media_search_result(media)),
        media_registry=registry,
        feedback=FakeFeedback(),
    )
    drive(ctx, _actions_state(media))
    # First render: no memory. Second render (after the toggle's RELOAD):
    # cursor restored to the toggled row's index.
    assert len(sel.start_indices) == 2
    assert sel.start_indices[0] is None
    assert sel.start_indices[1] is not None and sel.start_indices[1] > 0


def test_main_watching_works_logged_out_via_local_registry(
    polish_config, registry
):
    """The reported '❌ You haven't logged in' trap: personal lists must fall
    back to the local registry when unauthenticated."""
    from viu_media.libs.media_api.types import UserMediaListStatus

    media = make_media_item(id=9, title="Local Show", episodes=12)
    registry.update_media_index_entry(
        media_id=9, media_item=media, status=UserMediaListStatus.WATCHING
    )
    # Selecting "Watching (Local)" then the show itself: both selections only
    # succeed if the local list actually rendered them (FakeSelector asserts
    # picks exist among the choices).
    sel = FakeSelector([pick("Watching (Local)"), pick("Local Show")])
    feedback = FakeFeedback()
    ctx = make_context(
        config=polish_config,
        selector=sel,
        media_api=FakeApiClient(),  # user=None -> not authenticated
        media_registry=registry,
        feedback=feedback,
    )
    drive(ctx, make_state("main"))
    errors = [m for m in feedback.messages if m[0] == "error"]
    assert not errors, f"unexpected errors: {errors}"


def test_episodes_menu_cursor_lands_on_history_episode(polish_config):
    media = make_media_item(id=1, title="Test Anime", episodes=3)
    provider = FakeAnimeProvider(
        anime=make_anime(id="anime-1", title="Test Anime", episodes=["1", "2", "3"])
    )
    sel = FakeSelector(["Back"])
    ctx = make_context(
        config=polish_config,
        selector=sel,
        media_api=FakeApiClient(search_result=make_media_search_result(media)),
        provider=provider,
        player=FakePlayerService(),
        feedback=FakeFeedback(),
        watch_history=FakeWatchHistory(resume=("2", None)),
    )
    import viu_media.cli.interactive.menu.media._source_fallback as sf

    state = make_state(
        "episodes",
        media_api={"search_result": {media.id: media}, "media_id": media.id},
        provider={"anime": provider.anime},
    )
    import unittest.mock as mock

    with mock.patch.object(sf, "nyaa_extra_episodes", lambda *a, **k: []):
        drive(ctx, [make_state("main"), state])
    # Cursor starts on episode "2" (index 1), the natural next episode.
    assert sel.start_indices and sel.start_indices[0] == 1


class _FakeDownload:
    def __init__(self):
        self.downloaded: list = []

    def download_episodes_sync(self, media_item, episodes):
        self.downloaded.append((media_item.id, list(episodes)))


def test_download_all_episodes_in_one_action(polish_config):
    """The reported gap: a 50-episode season needed 50 TAB presses. 'All
    episodes' downloads the lot in one confirmed action."""
    media = make_media_item(id=1, title="Test Anime", episodes=12)
    eps = [str(i) for i in range(1, 13)]
    provider = FakeAnimeProvider(
        anime=make_anime(id="anime-1", title="Test Anime", episodes=eps)
    )
    dl = _FakeDownload()
    sel = FakeSelector([pick("All episodes"), pick("Yes, download them")])
    ctx = make_context(
        config=polish_config,
        selector=sel,
        media_api=FakeApiClient(search_result=make_media_search_result(media)),
        provider=provider,
        download=dl,
        feedback=FakeFeedback(),
    )
    state = make_state(
        "download_episodes",
        media_api={"search_result": {media.id: media}, "media_id": media.id},
    )
    drive(ctx, [make_state("main"), state])
    assert dl.downloaded == [(1, eps)]
