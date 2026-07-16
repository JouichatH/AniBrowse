"""Tests for enabling skip + delivering AniSkip intervals to the clean mpv path."""

import dataclasses
import json
import time

from viu_media.cli.service.player.aniskip import SkipInterval
from viu_media.cli.service.player import service as service_mod
from viu_media.cli.service.player.service import PlayerService
from viu_media.libs.player.mpv.player import (
    _action_for_exit_code,
    _viu_lua_args,
)
from viu_media.libs.player.params import PlayerParams
from viu_media.core.config import AppConfig


def _params():
    return PlayerParams(url="u", title="t", query="q", episode="3")


def _read_skip_json_when_done(path, timeout=2.0):
    """Wait for the background fetch thread to finish, then return the payload."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("done"):
                return data
        except (OSError, ValueError):
            pass
        time.sleep(0.01)
    raise AssertionError(f"skip json never marked done: {path}")


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


def test_lua_servers_json_opt_present_only_when_set():
    # No servers_json -> the Lua's Ctrl+S binding stays off (opt omitted).
    opts = next(a for a in _viu_lua_args(_params()) if a.startswith("--script-opts="))
    assert "viu_skip-servers_json" not in opts

    params = dataclasses.replace(_params(), servers_json="C:/cache/servers.json")
    opts = next(a for a in _viu_lua_args(params) if a.startswith("--script-opts="))
    assert "viu_skip-servers_json=C:/cache/servers.json" in opts


def test_lua_skip_json_opt_present_only_when_set():
    opts = next(a for a in _viu_lua_args(_params()) if a.startswith("--script-opts="))
    assert "viu_skip-skip_json" not in opts

    params = dataclasses.replace(_params(), skip_json="C:/cache/skip.json")
    opts = next(a for a in _viu_lua_args(params) if a.startswith("--script-opts="))
    assert "viu_skip-skip_json=C:/cache/skip.json" in opts


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


def test_with_skip_enables_and_delivers_intervals_via_file(monkeypatch, tmp_path):
    # AniSkip is off the launch path now: _with_skip returns immediately with skip
    # enabled and a skip_json path; the intervals land in that file asynchronously.
    skip_path = str(tmp_path / "skip.json")
    monkeypatch.setattr(service_mod, "_skip_json_path", lambda: skip_path)
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

    # Launch params carry no intervals (they're delivered via file), but skip is
    # enabled and the file path is set.
    assert out.skip_op is None and out.skip_ed is None
    assert out.skip_op_enabled is True and out.skip_ed_enabled is True
    assert out.skip_json == skip_path

    data = _read_skip_json_when_done(skip_path)
    assert data["op"] == [80.0, 110.0]
    assert data["ed"] == [1300.0, 1400.0]


def test_with_skip_respects_disabled_ending(monkeypatch, tmp_path):
    skip_path = str(tmp_path / "skip.json")
    monkeypatch.setattr(service_mod, "_skip_json_path", lambda: skip_path)
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
    assert out.skip_ed_enabled is False

    data = _read_skip_json_when_done(skip_path)
    assert data["op"] == [80.0, 110.0]
    assert data["ed"] is None  # ending disabled -> not written


def test_with_skip_noop_when_both_disabled():
    svc, _ = _service(opening_skip=False, ending_skip=False)
    params = _params()
    assert svc._with_skip(params, _Media()) is params


def test_with_skip_without_mal_id_still_enables_for_chapter_fallback(
    monkeypatch, tmp_path
):
    # No MAL id -> no AniSkip fetch, but skip stays enabled so the Lua's
    # chapter-title fallback can still act. The file is written done immediately.
    skip_path = str(tmp_path / "skip.json")
    monkeypatch.setattr(service_mod, "_skip_json_path", lambda: skip_path)
    svc, _ = _service(opening_skip=True, ending_skip=True)

    class NoMal:
        id_mal = None

    out = svc._with_skip(_params(), NoMal())
    assert out.skip_op is None and out.skip_ed is None
    assert out.skip_op_enabled is True and out.skip_ed_enabled is True
    assert out.skip_json == skip_path

    data = _read_skip_json_when_done(skip_path)
    assert data["op"] is None and data["ed"] is None and data["done"] is True
