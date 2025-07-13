from pathlib import Path
from unittest.mock import patch

import pytest
from fastanime.cli.config.loader import ConfigLoader
from fastanime.cli.config.model import AppConfig, GeneralConfig
from fastanime.core.exceptions import ConfigError

# ==============================================================================
# Pytest Fixtures
# ==============================================================================


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Creates a temporary directory for config files for each test."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def valid_config_content() -> str:
    """Provides the content for a valid, complete config.ini file."""
    return """
[general]
provider = hianime
selector = fzf
auto_select_anime_result = false
icons = true
preview = text
image_renderer = icat
preferred_language = romaji
sub_lang = jpn
manga_viewer = feh
downloads_dir = ~/MyAnimeDownloads
check_for_updates = false
cache_requests = false
max_cache_lifetime = 01:00:00
normalize_titles = false
discord = true

[stream]
player = vlc
quality = 720
translation_type = dub
server = gogoanime
auto_next = true
continue_from_watch_history = false
preferred_watch_history = remote
auto_skip = true
episode_complete_at = 95
ytdlp_format = best

[anilist]
per_page = 25
sort_by = TRENDING_DESC
default_media_list_tracking = track
force_forward_tracking = false
recent = 10

[fzf]
opts = --reverse --height=80%
header_color = 255,0,0
preview_header_color = 0,255,0
preview_separator_color = 0,0,255

[rofi]
theme_main = /path/to/main.rasi
theme_preview = /path/to/preview.rasi
theme_confirm = /path/to/confirm.rasi
theme_input = /path/to/input.rasi

[mpv]
args = --fullscreen
pre_args =
disable_popen = false
use_python_mpv = true
"""


@pytest.fixture
def partial_config_content() -> str:
    """Provides content for a partial config file to test default value handling."""
    return """
[general]
provider = hianime

[stream]
quality = 720
"""


@pytest.fixture
def malformed_ini_content() -> str:
    """Provides content with invalid .ini syntax that configparser will fail on."""
    return "[general\nkey = value"


# ==============================================================================
# Test Class for ConfigLoader
# ==============================================================================


class TestConfigLoader:
    def test_load_creates_and_loads_default_config(self, temp_config_dir: Path):
        """
        GIVEN no config file exists.
        WHEN the ConfigLoader loads configuration.
        THEN it should create a default config file and load default values.
        """
        # ARRANGE
        config_path = temp_config_dir / "config.ini"
        assert not config_path.exists()
        loader = ConfigLoader(config_path=config_path)

        # ACT: Mock click.echo to prevent printing during tests
        with patch("click.echo"):
            config = loader.load()

        # ASSERT: File creation and content
        assert config_path.exists()
        created_content = config_path.read_text(encoding="utf-8")
        assert "[general]" in created_content
        assert "# Configuration for general application behavior" in created_content

        # ASSERT: Loaded object has default values.
        # Direct object comparison can be brittle, so we test key attributes.
        default_config = AppConfig.model_validate({})
        assert config.general.provider == default_config.general.provider
        assert config.stream.quality == default_config.stream.quality
        assert config.anilist.per_page == default_config.anilist.per_page
        # A full comparison might fail due to how Path objects or multi-line strings
        # are instantiated vs. read from a file. Testing key values is more robust.

    def test_load_from_valid_full_config(
        self, temp_config_dir: Path, valid_config_content: str
    ):
        """
        GIVEN a valid and complete config file exists.
        WHEN the ConfigLoader loads it.
        THEN it should return a correctly parsed AppConfig object with overridden values.
        """
        # ARRANGE
        config_path = temp_config_dir / "config.ini"
        config_path.write_text(valid_config_content)
        loader = ConfigLoader(config_path=config_path)

        # ACT
        config = loader.load()

        # ASSERT
        assert isinstance(config, AppConfig)
        assert config.general.provider == "hianime"
        assert config.general.auto_select_anime_result is False
        assert config.general.downloads_dir == Path("~/MyAnimeDownloads")
        assert config.stream.quality == "720"
        assert config.stream.player == "vlc"
        assert config.anilist.per_page == 25
        assert config.fzf.opts == "--reverse --height=80%"
        assert config.mpv.use_python_mpv is True

    def test_load_from_partial_config(
        self, temp_config_dir: Path, partial_config_content: str
    ):
        """
        GIVEN a partial config file exists.
        WHEN the ConfigLoader loads it.
        THEN it should load specified values and use defaults for missing ones.
        """
        # ARRANGE
        config_path = temp_config_dir / "config.ini"
        config_path.write_text(partial_config_content)
        loader = ConfigLoader(config_path=config_path)

        # ACT
        config = loader.load()

        # ASSERT: Specified values are loaded correctly
        assert config.general.provider == "hianime"
        assert config.stream.quality == "720"

        # ASSERT: Other values fall back to defaults
        default_general = GeneralConfig()
        assert config.general.selector == default_general.selector
        assert config.general.icons is False
        assert config.stream.player == "mpv"
        assert config.anilist.per_page == 15

    @pytest.mark.parametrize(
        "value, expected",
        [
            ("true", True),
            ("false", False),
            ("yes", True),
            ("no", False),
            ("on", True),
            ("off", False),
            ("1", True),
            ("0", False),
        ],
    )
    def test_boolean_value_handling(
        self, temp_config_dir: Path, value: str, expected: bool
    ):
        """
        GIVEN a config file with various boolean string representations.
        WHEN the ConfigLoader loads it.
        THEN pydantic should correctly parse them into boolean values.
        """
        # ARRANGE
        content = f"[general]\nauto_select_anime_result = {value}\n"
        config_path = temp_config_dir / "config.ini"
        config_path.write_text(content)
        loader = ConfigLoader(config_path=config_path)

        # ACT
        config = loader.load()

        # ASSERT
        assert config.general.auto_select_anime_result is expected

    def test_load_raises_error_for_malformed_ini(
        self, temp_config_dir: Path, malformed_ini_content: str
    ):
        """
        GIVEN a config file has invalid .ini syntax that configparser will reject.
        WHEN the ConfigLoader loads it.
        THEN it should raise a ConfigError.
        """
        # ARRANGE
        config_path = temp_config_dir / "config.ini"
        config_path.write_text(malformed_ini_content)
        loader = ConfigLoader(config_path=config_path)

        # ACT & ASSERT
        with pytest.raises(ConfigError, match="Error parsing configuration file"):
            loader.load()

    def test_load_raises_error_for_invalid_value(self, temp_config_dir: Path):
        """
        GIVEN a config file contains a value that fails model validation.
        WHEN the ConfigLoader loads it.
        THEN it should raise a ConfigError with a helpful message.
        """
        # ARRANGE
        invalid_content = "[stream]\nquality = 9001\n"
        config_path = temp_config_dir / "config.ini"
        config_path.write_text(invalid_content)
        loader = ConfigLoader(config_path=config_path)

        # ACT & ASSERT
        with pytest.raises(ConfigError) as exc_info:
            loader.load()

        # Check for a user-friendly error message
        assert "Configuration error" in str(exc_info.value)
        assert "stream.quality" in str(exc_info.value)

    def test_load_raises_error_if_default_config_cannot_be_written(
        self, temp_config_dir: Path
    ):
        """
        GIVEN the default config file cannot be written due to permissions.
        WHEN the ConfigLoader attempts to create it.
        THEN it should raise a ConfigError.
        """
        # ARRANGE
        config_path = temp_config_dir / "unwritable_dir" / "config.ini"
        loader = ConfigLoader(config_path=config_path)

        # ACT & ASSERT: Mock Path.write_text to simulate a permissions error
        with patch("pathlib.Path.write_text", side_effect=PermissionError):
            with patch("click.echo"):  # Mock echo to keep test output clean
                with pytest.raises(ConfigError) as exc_info:
                    loader.load()

        assert "Could not create default configuration file" in str(exc_info.value)
        assert "Please check permissions" in str(exc_info.value)
