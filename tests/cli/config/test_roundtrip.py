"""Config round-trip: generate(default) -> load must reproduce the defaults.

This guards the two halves that drift most - the TOML generator and the
Pydantic loader - against escaping / None / path-quoting regressions.
"""

import tomllib

import pytest

from viu_media.cli.config.generate import generate_config_toml_from_app_model
from viu_media.cli.config.loader import ConfigLoader
from viu_media.core.config import AppConfig


def _roundtrip(config: AppConfig, tmp_path) -> AppConfig:
    toml_text = generate_config_toml_from_app_model(config)
    # The generated file must at least be valid TOML.
    tomllib.loads(toml_text)
    path = tmp_path / "config.toml"
    path.write_text(toml_text, encoding="utf-8")
    return ConfigLoader(config_path=path).load(allow_setup=False)


def test_defaults_roundtrip(tmp_path):
    original = AppConfig()
    loaded = _roundtrip(original, tmp_path)
    assert loaded == original


def test_windows_path_survives_roundtrip(tmp_path):
    # A backslash-laden Windows path is the classic TOML escaping trap. Build via
    # model_validate so the field is a real Path (plain assignment skips coercion).
    original = AppConfig.model_validate(
        {"downloads": {"downloads_dir": r"C:\Users\test\Anime Downloads"}}
    )
    loaded = _roundtrip(original, tmp_path)
    assert loaded.downloads.downloads_dir == original.downloads.downloads_dir
    assert loaded == original


def test_modified_scalar_values_roundtrip(tmp_path):
    original = AppConfig()
    original.stream.auto_next = True
    original.stream.opening_skip = True
    original.stream.ending_skip = True
    original.general.icons = not original.general.icons
    loaded = _roundtrip(original, tmp_path)
    assert loaded.stream.auto_next is True
    assert loaded.stream.opening_skip is True
    assert loaded.stream.ending_skip is True
    assert loaded == original


def test_string_with_quotes_roundtrips(tmp_path):
    original = AppConfig()
    # A free-form string field stuffed with quotes/brackets - TOML escaping trap.
    original.stream.ytdlp_format = 'best[height<=720] "quoted" \\slash'
    loaded = _roundtrip(original, tmp_path)
    assert loaded.stream.ytdlp_format == original.stream.ytdlp_format
