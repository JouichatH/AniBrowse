"""Smoke tests proving the headless harness can drive the real session loop."""

from tests.conftest import drive, make_context, make_state
from tests.support.fakes import (
    FakeApiClient,
    FakeFeedback,
    FakeSelector,
    pick,
)
from viu_media.libs.media_api.params import MediaSearchParams


def test_exit_option_ends_loop_without_popping(app_config):
    ctx = make_context(
        config=app_config,
        selector=FakeSelector([pick("Exit")]),
        media_api=FakeApiClient(),
        feedback=FakeFeedback(),
    )
    final = drive(ctx, make_state("main"))
    # EXIT breaks the loop; the root state is still on the stack.
    assert len(final) == 1


def test_exhausted_script_escapes_all_the_way_out(app_config):
    """An empty script = Esc at every prompt; Esc at the root quits."""
    ctx = make_context(
        config=app_config,
        selector=FakeSelector([]),
        media_api=FakeApiClient(),
        feedback=FakeFeedback(),
    )
    final = drive(ctx, make_state("main"))
    assert final == []


def test_search_flow_reaches_results_menu(app_config):
    selector = FakeSelector([pick("Search"), "one piece"])
    api = FakeApiClient()
    ctx = make_context(
        config=app_config,
        selector=selector,
        media_api=api,
        feedback=FakeFeedback(),
    )
    final = drive(ctx, make_state("main"))

    search_calls = [c for c in api.calls if c[0] == "search_media"]
    assert search_calls, "main menu Search should call media_api.search_media"
    params = search_calls[0][1]
    assert isinstance(params, MediaSearchParams)
    assert params.query == "one piece"

    # After the scripted answers ran out the flow escaped cleanly (no dead end).
    assert final == []

    # The loop really dispatched a second menu (RESULTS) after MAIN.
    prompts = [call[1] for call in selector.calls]
    assert len(prompts) >= 3, f"expected to reach the results menu, saw: {prompts}"
