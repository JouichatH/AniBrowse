"""Tests for baking AniSkip intervals into the clean (non-IPC) mpv launch."""

import dataclasses

from viu_media.cli.service.player.aniskip import SkipInterval
from viu_media.cli.service.player.service import PlayerService
from viu_media.libs.player.mpv.player import _skip_script_args
from viu_media.libs.player.params import PlayerParams
from viu_media.core.config import AppConfig


def _params():
    return PlayerParams(url="u", title="t", query="q", episode="3")


# ---- _skip_script_args (mpv arg construction) ----------------------------


def test_no_skip_args_when_no_intervals():
    assert _skip_script_args(_params()) == []


def test_skip_args_include_script_and_opts():
    params = dataclasses.replace(_params(), skip_op=(80.0, 110.0), skip_ed=(1300.0, 1400.0))
    args = _skip_script_args(params)
    assert any(a.startswith("--script=") and a.endswith("viu_skip.lua") for a in args)
    opts = next(a for a in args if a.startswith("--script-opts="))
    assert "viu_skip-op_start=80.0" in opts
    assert "viu_skip-op_end=110.0" in opts
    assert "viu_skip-ed_start=1300.0" in opts
    assert "viu_skip-ed_end=1400.0" in opts


def test_only_opening_leaves_ending_disabled():
    params = dataclasses.replace(_params(), skip_op=(80.0, 110.0))
    opts = next(a for a in _skip_script_args(params) if a.startswith("--script-opts="))
    assert "viu_skip-op_start=80.0" in opts
    assert "viu_skip-ed_start=-1" in opts


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


def test_with_skip_noop_without_mal_id():
    svc, _ = _service(opening_skip=True)
    params = _params()

    class NoMal:
        id_mal = None

    assert svc._with_skip(params, NoMal()) is params
