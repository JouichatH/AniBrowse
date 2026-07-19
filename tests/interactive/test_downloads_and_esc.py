"""Regressions for the Downloads-library and nested-prompt-Esc review round.

1. The Downloads menu is a real offline library: it lists only shows with
   downloaded episodes, opens their downloaded-episode list, and guides the
   user toward the Download action when the library is empty (it used to
   mirror every registry category and offer online streaming).
2. Esc inside a nested prompt (e.g. "Select list status" under Add/Update
   List) cancels that action and re-shows the menu that spawned it - it used
   to propagate to the session loop and pop that menu too, skipping a level.
"""

import pytest

from tests.conftest import drive, make_context, make_state
from tests.support.fakes import (
    FakeApiClient,
    FakeFeedback,
    FakeSelector,
    make_media_item,
    make_media_search_result,
    pick,
)
from viu_media.core.config import AppConfig
from viu_media.core.exceptions import NavigationAbort


@pytest.fixture
def cfg():
    c = AppConfig()
    c.general.icons = False
    c.general.preview = "none"
    c.stream.continue_from_watch_history = False
    return c


@pytest.fixture
def registry(tmp_path):
    from viu_media.cli.service.registry.service import MediaRegistryService

    c = AppConfig()
    c.media_registry.media_dir = tmp_path / "media"
    c.media_registry.index_dir = tmp_path / "index"
    return MediaRegistryService("anilist", c.media_registry)


def esc(choices):
    """Script entry simulating Esc: what a real selector raises on abort."""
    raise NavigationAbort()


def _actions_state(media):
    return make_state(
        "media_actions",
        media_api={"search_result": {media.id: media}, "media_id": media.id},
    )


# ---- Esc in nested prompts ------------------------------------------------


def test_sub_prompts_swallow_navigation_abort():
    from viu_media.cli.interactive.menu.media._prompts import (
        sub_choose,
        sub_choose_multiple,
    )

    exhausted = FakeSelector([])  # empty script -> raises NavigationAbort
    assert sub_choose(exhausted, "p", ["a"]) is None
    exhausted = FakeSelector([])
    assert sub_choose_multiple(exhausted, "p", ["a"]) == []


def test_esc_on_list_status_returns_to_media_actions(cfg, registry):
    """The reported bug: Esc on 'Select list status' skipped past the
    'Select Action' page straight to the results list."""
    media = make_media_item(id=1, title="Test Anime", episodes=3)
    sel = FakeSelector([pick("Add/Update List"), esc])
    ctx = make_context(
        config=cfg,
        selector=sel,
        media_api=FakeApiClient(search_result=make_media_search_result(media)),
        media_registry=registry,
        feedback=FakeFeedback(),
    )
    drive(ctx, [make_state("main"), _actions_state(media)])
    prompts = [c[1] for c in sel.calls if c[0] == "choose"]
    i = prompts.index("Select list status")
    assert prompts[i + 1] == "Select Action"


def test_esc_on_change_provider_returns_to_media_actions(cfg, registry):
    media = make_media_item(id=1, title="Test Anime", episodes=3)
    sel = FakeSelector([pick("Change Provider"), esc])
    ctx = make_context(
        config=cfg,
        selector=sel,
        media_api=FakeApiClient(search_result=make_media_search_result(media)),
        media_registry=registry,
        feedback=FakeFeedback(),
    )
    drive(ctx, [make_state("main"), _actions_state(media)])
    prompts = [c[1] for c in sel.calls if c[0] == "choose"]
    i = prompts.index("Select Provider")
    assert prompts[i + 1] == "Select Action"


# ---- Downloads library ----------------------------------------------------


def test_downloads_menu_empty_guides_to_download(cfg, registry):
    """Empty library: explain how to download instead of showing category
    pages full of merely-watched shows."""
    from viu_media.libs.media_api.types import UserMediaListStatus

    watched = make_media_item(id=2, title="Only Watched", episodes=12)
    registry.update_media_index_entry(
        media_id=2, media_item=watched, status=UserMediaListStatus.WATCHING
    )

    sel = FakeSelector([pick("Downloads")])
    feedback = FakeFeedback()
    ctx = make_context(
        config=cfg,
        selector=sel,
        media_api=FakeApiClient(),
        media_registry=registry,
        feedback=feedback,
    )
    drive(ctx, make_state("main"))

    infos = [m for m in feedback.messages if m[0] == "info"]
    assert any("empty" in m[1].lower() for m in infos)
    assert any("'Download'" in (m[2] or "") for m in infos)
    # The old category clones must be gone from every prompt shown.
    for _, _, choices in sel.calls:
        for choice in choices or []:
            assert "Trending (Local)" not in choice
            assert "Only Watched" not in choice


def test_downloads_menu_lists_only_downloaded_shows(cfg, registry, tmp_path):
    """A show with a downloaded episode appears (with its count) and opens the
    offline episode list; watched-but-not-downloaded shows do not appear."""
    from viu_media.cli.service.registry.models import DownloadStatus
    from viu_media.libs.media_api.types import UserMediaListStatus

    watched = make_media_item(id=2, title="Only Watched", episodes=12)
    registry.update_media_index_entry(
        media_id=2, media_item=watched, status=UserMediaListStatus.WATCHING
    )

    downloaded = make_media_item(id=1, title="Test Anime", episodes=3)
    registry.update_media_index_entry(
        media_id=1, media_item=downloaded, status=UserMediaListStatus.WATCHING
    )
    episode_file = tmp_path / "ep1.mkv"
    episode_file.write_bytes(b"x")
    assert registry.update_episode_download_status(
        media_id=1,
        episode_number="1",
        status=DownloadStatus.COMPLETED,
        file_path=episode_file,
    )

    sel = FakeSelector([pick("Test Anime"), "Back"])
    ctx = make_context(
        config=cfg,
        selector=sel,
        media_api=FakeApiClient(),
        media_registry=registry,
        feedback=FakeFeedback(),
    )
    drive(ctx, [make_state("main"), make_state("downloads")])

    library_call = next(c for c in sel.calls if c[1] == "Downloads Library")
    labels = library_call[2]
    assert any("Test Anime (1 episode downloaded)" in label for label in labels)
    assert not any("Only Watched" in label for label in labels)

    episode_call = next(c for c in sel.calls if c[1] == "Select Episode")
    assert "1" in episode_call[2]
