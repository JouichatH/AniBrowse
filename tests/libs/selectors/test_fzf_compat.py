"""Old-fzf compatibility: distro builds (Ubuntu 24.04 LTS ships fzf 0.44)
must be able to run the shipped default opts, and an fzf that rejects its
options must surface an actionable error instead of an infinite relaunch
loop (exit 2 used to read as "no selection" -> menu RELOAD -> fzf again).
"""

import re
import subprocess

import pytest

from viu_media.core import exceptions
from viu_media.core.config import defaults
from viu_media.core.config.model import FzfConfig
from viu_media.libs.selectors.fzf import selector as fzf_mod


def test_default_fzf_opts_avoid_post_044_features():
    text = defaults.FZF_OPTS.read_text(encoding="utf-8")
    # toggle-wrap (the action) and --wrap (the flag) need fzf >= 0.54.
    assert "toggle-wrap" not in text
    assert not re.search(r"^--wrap\b", text, re.MULTILINE)


@pytest.fixture
def fzf_selector(monkeypatch):
    monkeypatch.setattr(fzf_mod.shutil, "which", lambda _: "/usr/bin/fzf")
    return fzf_mod.FzfSelector(FzfConfig())


def _completed(returncode: int) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["fzf"], returncode=returncode, stdout="")


def test_fzf_exit_2_raises_actionable_error(fzf_selector, monkeypatch):
    monkeypatch.setattr(fzf_mod.subprocess, "run", lambda *a, **k: _completed(2))
    with pytest.raises(exceptions.AniBrowseError, match="fzf"):
        fzf_selector.choose("p", ["a", "b"])
    with pytest.raises(exceptions.AniBrowseError, match="fzf"):
        fzf_selector.choose_multiple("p", ["a", "b"])


def test_fzf_exit_1_is_still_no_selection(fzf_selector, monkeypatch):
    monkeypatch.setattr(fzf_mod.subprocess, "run", lambda *a, **k: _completed(1))
    assert fzf_selector.choose("p", ["a", "b"]) is None
    assert fzf_selector.choose_multiple("p", ["a", "b"]) == []


def test_fzf_exit_130_still_aborts(fzf_selector, monkeypatch):
    monkeypatch.setattr(fzf_mod.subprocess, "run", lambda *a, **k: _completed(130))
    with pytest.raises(exceptions.NavigationAbort):
        fzf_selector.choose("p", ["a", "b"])
