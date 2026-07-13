"""Shared fixtures: build an injectable Context and drive menus headlessly.

The interactive app is testable because ``Context`` exposes every dependency
as a settable backing field (``_selector``, ``_player``, ...) and the session
dispatches menus via ``session._menus[name].execute(ctx, state)``. These
fixtures wire scripted fakes (tests/support/fakes.py) into those seams.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import pytest

from viu_media.core.config import AppConfig

_menus_loaded = False


def load_menus():
    """Load the media menu modules once per process (they self-register)."""
    global _menus_loaded
    from viu_media.cli.interactive.session import session

    if not _menus_loaded:
        session.load_menus_from_folder("media")
        _menus_loaded = True
    return session


def make_context(config: Optional[AppConfig] = None, **deps):
    """Context with fakes injected via its backing fields.

    ``make_context(selector=..., media_api=...)`` sets ``ctx._selector`` etc.
    Anything not injected lazily builds the real service - keep tests honest
    by injecting everything a flow touches.
    """
    from viu_media.cli.interactive.session import Context

    ctx = Context(config=config or AppConfig())
    for name, value in deps.items():
        attr = f"_{name}"
        if not hasattr(ctx, attr):
            raise AttributeError(f"Context has no dependency field {attr!r}")
        setattr(ctx, attr, value)
    return ctx


def make_state(
    menu: Union[str, "Any"],
    media_api: Optional[Dict[str, Any]] = None,
    provider: Optional[Dict[str, Any]] = None,
):
    """A frozen State for ``menu`` with sub-state given by alias kwargs."""
    from viu_media.cli.interactive.state import (
        MediaApiState,
        MenuName,
        ProviderState,
        State,
    )

    return State(
        menu_name=MenuName(menu.upper()) if isinstance(menu, str) else menu,
        media_api=MediaApiState(**(media_api or {})),
        provider=ProviderState(**(provider or {})),
    )


def drive(context, history, max_steps: int = 200) -> List:
    """Run the real session loop headlessly; returns the final history stack.

    Sets ``session._context``/``session._history`` directly - do NOT use
    ``session.run()``, which rebuilds the Context and drops the fakes.
    The loop ends when the selector script is exhausted (Esc all the way out),
    an EXIT directive fires, or the history empties.

    A step cap guards against a menu that loops forever (e.g. a RELOAD cycle):
    the test fails loudly instead of hanging the suite.
    """
    session = load_menus()
    if not isinstance(history, list):
        history = [history]
    session._context = context
    session._history = list(history)
    try:
        _run_loop_capped(session, max_steps)
        return list(session._history)
    finally:
        session._history = []


def _run_loop_capped(session, max_steps: int):
    """Faithfully mirror Session._run_main_loop but bounded, to catch runaway menus.

    The directive handling here must match session.py exactly (including the
    BACKXn ``len > n`` guards) so tests exercise real navigation semantics; the
    only addition is the step cap that turns a hang into a failed assertion.
    """
    from viu_media.cli.interactive.state import InternalDirective
    from viu_media.core.exceptions import NavigationAbort

    steps = 0
    while session._history:
        steps += 1
        if steps > max_steps:
            raise AssertionError(
                f"drive() exceeded {max_steps} steps at menu "
                f"{session._history[-1].menu_name} - likely a navigation loop"
            )
        current_state = session._history[-1]
        try:
            next_step = session._menus[current_state.menu_name].execute(
                session._context, current_state
            )
        except NavigationAbort:
            next_step = InternalDirective.BACK
        except KeyboardInterrupt:
            break

        if isinstance(next_step, InternalDirective):
            if next_step == InternalDirective.MAIN:
                session._history = [session._history[0]]
            elif next_step == InternalDirective.RELOAD:
                continue
            elif next_step == InternalDirective.CONFIG_EDIT:
                raise AssertionError("CONFIG_EDIT is not drivable headlessly")
            elif next_step == InternalDirective.BACK:
                session._history.pop()
            elif next_step == InternalDirective.BACKX2:
                if len(session._history) > 2:
                    session._history.pop()
                    session._history.pop()
            elif next_step == InternalDirective.BACKX3:
                if len(session._history) > 3:
                    session._history.pop()
                    session._history.pop()
                    session._history.pop()
            elif next_step == InternalDirective.BACKX4:
                if len(session._history) > 4:
                    for _ in range(4):
                        session._history.pop()
            elif next_step == InternalDirective.EXIT:
                break
        else:
            session._history.append(next_step)


@pytest.fixture
def app_config() -> AppConfig:
    cfg = AppConfig()
    cfg.general.icons = False
    return cfg


@pytest.fixture
def ipc_client_factory():
    """Factory for FakeIPCClient (records commands, serves scripted events)."""
    from tests.support.fakes import FakeIPCClient

    def _make(**kwargs):
        return FakeIPCClient(**kwargs)

    return _make


@pytest.fixture(autouse=True)
def _reset_session_state():
    """session._history is class-level state: keep tests independent."""
    from viu_media.cli.interactive.session import Session

    yield
    Session._history = []
