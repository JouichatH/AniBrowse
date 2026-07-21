"""config --refresh migration + corrupt-config self-healing.

Guards the two promises made to non-technical users:
- re-running the installer unpins terminal-detected UI fields that older
  builds froze into config.toml (preview = "none" from a conhost first run)
  and adopts new defaults (mpv fullscreen) without losing their choices;
- a config.toml with a typo (or a PowerShell-added UTF-8 BOM) never bricks
  the app: BOMs are tolerated, unparseable files are backed up and reset.
"""

import tomllib

from viu_media.cli.config.loader import ConfigLoader
from viu_media.core.config import AppConfig


def _parsed(path):
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_mpv_fullscreen_is_the_default():
    assert AppConfig().mpv.args == "--fullscreen"


def test_refresh_unpins_frozen_ui_fields(tmp_path):
    # A legacy config as an old build wrote it: detected values pinned.
    path = tmp_path / "config.toml"
    path.write_text(
        '[general]\npreview = "none"\nselector = "default"\nimage_renderer = "chafa"\n',
        encoding="utf-8",
    )
    ConfigLoader(config_path=path).refresh()
    general = _parsed(path).get("general", {})
    for field in ("preview", "selector", "image_renderer"):
        assert field not in general, f"{field} still pinned after refresh"
    # Left commented, so live detection applies at every launch.
    text = path.read_text(encoding="utf-8")
    for field in ("preview", "selector", "image_renderer"):
        assert f"# {field} = " in text, field


def test_refresh_adopts_new_mpv_default(tmp_path):
    # args = "" is the OLD default, not a user choice - the new default wins.
    path = tmp_path / "config.toml"
    path.write_text('[mpv]\nargs = ""\n', encoding="utf-8")
    refreshed = ConfigLoader(config_path=path).refresh()
    assert refreshed is not None
    assert refreshed.mpv.args == "--fullscreen"
    assert _parsed(path)["mpv"]["args"] == "--fullscreen"


def test_refresh_preserves_user_choices(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        "[general]\nicons = false\n\n"
        '[mpv]\nargs = "--volume=50"\n\n'
        "[stream]\nauto_next = true\n",
        encoding="utf-8",
    )
    refreshed = ConfigLoader(config_path=path).refresh()
    assert refreshed is not None
    assert refreshed.general.icons is False
    assert refreshed.mpv.args == "--volume=50"
    assert refreshed.stream.auto_next is True


def test_refresh_without_config_is_a_noop(tmp_path):
    path = tmp_path / "config.toml"
    assert ConfigLoader(config_path=path).refresh() is None
    assert not path.exists()


def test_bom_prefixed_config_loads(tmp_path):
    # PowerShell 5.1's `Set-Content -Encoding utf8` prepends a BOM, which
    # strict TOML rejects at line 1 column 1. utf-8-sig must absorb it.
    path = tmp_path / "config.toml"
    path.write_text("﻿[general]\nicons = false\n", encoding="utf-8")
    loaded = ConfigLoader(config_path=path).load(allow_setup=False)
    assert loaded.general.icons is False
    assert not (tmp_path / "config.toml.bak").exists()  # no reset needed


def test_corrupt_config_self_heals_on_load(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[mpv]\nargs --fullscreen\n", encoding="utf-8")  # missing '='
    loaded = ConfigLoader(config_path=path).load(allow_setup=False)
    # The app comes up on defaults instead of raising ConfigError...
    assert loaded == AppConfig()
    # ...the broken file is preserved for the user...
    backup = tmp_path / "config.toml.bak"
    assert backup.exists()
    assert "args --fullscreen" in backup.read_text(encoding="utf-8")
    # ...and the regenerated file parses cleanly.
    _parsed(path)
