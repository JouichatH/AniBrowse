"""Config round-trip: generate(default) -> load must reproduce the defaults.

This guards the two halves that drift most - the TOML generator and the
Pydantic loader - against escaping / None / path-quoting regressions.
"""

import tomllib


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


def test_env_detected_fields_are_commented_out(tmp_path):
    """selector / preview / image_renderer must NOT be frozen into the file.

    Writing the detected value would pin whatever terminal the first run
    happened in (e.g. preview = "none" from the installer's conhost window).
    Left commented, the loader's default_factory re-detects them every launch.
    """
    toml_text = generate_config_toml_from_app_model(AppConfig())
    parsed = tomllib.loads(toml_text)
    for field in ("selector", "preview", "image_renderer"):
        assert field not in parsed["general"], field
        assert f"# {field} = " in toml_text, field


def test_explicit_env_detected_choice_is_pinned(tmp_path):
    """A value that differs from live detection is a user choice - keep it."""
    original = AppConfig()
    pinned = "text" if original.general.preview != "text" else "image"
    original.general.preview = pinned
    toml_text = generate_config_toml_from_app_model(original)
    parsed = tomllib.loads(toml_text)
    assert parsed["general"]["preview"] == pinned
    loaded = _roundtrip(original, tmp_path)
    assert loaded.general.preview == pinned


def test_string_with_quotes_roundtrips(tmp_path):
    original = AppConfig()
    # A free-form string field stuffed with quotes/brackets - TOML escaping trap.
    original.stream.ytdlp_format = 'best[height<=720] "quoted" \\slash'
    loaded = _roundtrip(original, tmp_path)
    assert loaded.stream.ytdlp_format == original.stream.ytdlp_format
