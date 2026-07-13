"""Tests for baking AniSkip intervals into the clean (non-IPC) mpv launch."""

import dataclasses

from viu_media.cli.service.player.aniskip import SkipInterval
from viu_media.cli.service.player.service import PlayerService
from viu_media.libs.player.mpv.player import (
    _action_for_exit_code,
    _viu_lua_args,
)
from viu_media.libs.player.params import PlayerParams
from viu_media.core.config import AppConfig


def _params():
    return PlayerParams(url="u", title="t", query="q", episode="3")


# ---- _viu_lua_args (mpv arg construction) --------------------------------


def test_lua_always_loaded_for_nav_keys():
    # Even with no skip, the Lua loads so Shift+N/P navigation works.
    args = _viu_lua_args(_params())
    assert any(a.startswith("--script=") and a.endswith("viu_skip.lua") for a in args)
    opts = next(a for a in args if a.startswith("--script-opts="))
    assert "viu_skip-nav_keys=yes" in opts
    assert "viu_skip-op_enabled=no" in opts
    assert "viu_skip-ed_enabled=no" in opts


def test_lua_passes_intervals_and_enabled_flags():
    params = dataclasses.replace(
        _params(),
        skip_op=(80.0, 110.0),
        skip_ed=(1300.0, 1400.0),
        skip_op_enabled=True,
        skip_ed_enabled=True,
    )
    opts = next(a for a in _viu_lua_args(params) if a.startswith("--script-opts="))
    assert "viu_skip-op_enabled=yes" in opts
    assert "viu_skip-ed_enabled=yes" in opts
    assert "viu_skip-op_start=80.0" in opts
    assert "viu_skip-ed_end=1400.0" in opts


def test_enabled_without_interval_still_marks_enabled():
    # Chapter-based skip: enabled but AniSkip had no interval -> start stays -1.
    params = dataclasses.replace(_params(), skip_op_enabled=True)
    opts = next(a for a in _viu_lua_args(params) if a.startswith("--script-opts="))
    assert "viu_skip-op_enabled=yes" in opts
    assert "viu_skip-op_start=-1" in opts


# ---- exit code -> navigation action --------------------------------------


def test_exit_codes_map_to_actions():
    assert _action_for_exit_code(100) == "next"
    assert _action_for_exit_code(101) == "previous"
    assert _action_for_exit_code(0) is None
    assert _action_for_exit_code(None) is None


# ---- PlayerService._with_skip (fetch + attach) ---------------------------


class _Media:
    id_mal = 4321


def _service(**stream_overrides):
    cfg = AppConfig()
    for k, v in stream_overrides.items():
        setattr(cfg.stream, k, v)
    # provider/registry unused for _with_skip.
    return PlayerService(cfg, provider=None), cfg  # type: ignore[arg-type]


def test_with_skip_attaches_enabled_intervals(monkeypatch):
    svc, _ = _service(opening_skip=True, ending_skip=True)
    intervals = [
        SkipInterval(kind="op", start=80.0, end=110.0),
        SkipInterval(kind="ed", start=1300.0, end=1400.0),
    ]
    monkeypatch.setattr(
        "viu_media.cli.service.player.aniskip.fetch_skip_times",
        lambda *a, **k: intervals,
    )
    out = svc._with_skip(_params(), _Media())
    assert out.skip_op == (80.0, 110.0)
    assert out.skip_ed == (1300.0, 1400.0)


def test_with_skip_respects_disabled_ending(monkeypatch):
    svc, _ = _service(opening_skip=True, ending_skip=False)
    intervals = [
        SkipInterval(kind="op", start=80.0, end=110.0),
        SkipInterval(kind="ed", start=1300.0, end=1400.0),
    ]
    monkeypatch.setattr(
        "viu_media.cli.service.player.aniskip.fetch_skip_times",
        lambda *a, **k: intervals,
    )
    out = svc._with_skip(_params(), _Media())
    assert out.skip_op == (80.0, 110.0)
    assert out.skip_ed is None


def test_with_skip_noop_when_both_disabled():
    svc, _ = _service(opening_skip=False, ending_skip=False)
    params = _params()
    assert svc._with_skip(params, _Media()) is params


def test_with_skip_without_mal_id_still_enables_for_chapter_fallback():
    # No MAL id -> no AniSkip intervals, but skip stays enabled so the Lua's
    # chapter-title fallback can still act.
    svc, _ = _service(opening_skip=True, ending_skip=True)

    class NoMal:
        id_mal = None

    out = svc._with_skip(_params(), NoMal())
    assert out.skip_op is None and out.skip_ed is None
    assert out.skip_op_enabled is True and out.skip_ed_enabled is True
