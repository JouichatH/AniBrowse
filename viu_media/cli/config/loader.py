import logging
import tomllib
from pathlib import Path
from typing import Dict

import click
from pydantic import ValidationError

from ...core.config import AppConfig
from ...core.constants import USER_CONFIG
from ...core.exceptions import ConfigError

logger = logging.getLogger(__name__)

# Old defaults that newer builds replaced. A config still carrying the OLD
# default was never a deliberate user choice - refresh() drops the key so the
# new default applies (e.g. mpv now opens fullscreen out of the box).
LEGACY_DEFAULTS: dict[tuple[str, str], object] = {
    ("mpv", "args"): "",
}


class ConfigLoader:
    """
    Handles loading the application configuration from a .toml file.

    It ensures a default configuration exists, reads the .toml file,
    and uses Pydantic to parse and validate the data into a type-safe
    AppConfig object.
    """

    def __init__(self, config_path: Path = USER_CONFIG):
        """
        Initializes the loader with the path to the configuration file.

        Args:
            config_path: The path to the user's config.toml file.
        """
        self.config_path = config_path

    def _handle_first_run(self) -> AppConfig:
        """Handles the configuration process when no config.toml file is found."""
        click.echo(
            "[bold yellow]Welcome to Ani-Browse![/bold yellow] No configuration file found."
        )
        from InquirerPy import inquirer

        from .editor import InteractiveConfigEditor
        from .generate import generate_config_toml_from_app_model

        choice = inquirer.select(  # type: ignore
            message="How would you like to proceed?",
            choices=[
                "Use default settings (Recommended for new users)",
                "Configure settings interactively",
            ],
            default="Use default settings (Recommended for new users)",
        ).execute()

        if "interactively" in choice:
            editor = InteractiveConfigEditor(AppConfig())
            app_config = editor.run()
        else:
            app_config = AppConfig()

        config_toml_content = generate_config_toml_from_app_model(app_config)
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(config_toml_content, encoding="utf-8")
            click.echo(
                f"Configuration file created at: [green]{self.config_path}[/green]"
            )
        except Exception as e:
            raise ConfigError(
                f"Could not create configuration file at {self.config_path!s}. "
                f"Please check permissions. Error: {e}",
            )

        return app_config

    def _parse_or_recover(self) -> Dict:
        """Parse config.toml; if the TOML is unparseable, back it up and reset.

        utf-8-sig tolerates a UTF-8 BOM (Windows editors and PowerShell's
        `Set-Content -Encoding utf8` prepend one, which strict TOML rejects).
        A file that still fails to parse is copied to config.toml.bak and
        replaced with generated defaults - a typo in the config must never
        brick the app.
        """
        text = self.config_path.read_text(encoding="utf-8-sig")
        try:
            return tomllib.loads(text)
        except tomllib.TOMLDecodeError as e:
            from .generate import generate_config_toml_from_app_model

            backup = self.config_path.with_suffix(".toml.bak")
            backup.write_text(text, encoding="utf-8")
            self.config_path.write_text(
                generate_config_toml_from_app_model(AppConfig()), encoding="utf-8"
            )
            click.echo(
                f"Your config file had an error and was reset to defaults ({e}).\n"
                f"The old file was saved to: {backup}",
                err=True,
            )
            logger.warning(f"Recovered from unparseable config: {e}")
            return {}

    def refresh(self) -> "AppConfig | None":
        """Rewrite config.toml keeping user choices while unpinning stale values.

        Older builds froze terminal-detected fields (preview / selector /
        image_renderer) into the file at first run, pinning whatever terminal
        the installer happened to run in (e.g. preview = "none" from conhost).
        This drops those keys plus any value still equal to an old default
        (LEGACY_DEFAULTS), then regenerates the file, so live detection and
        new defaults apply again. Returns None when there is no config file.
        """
        if not self.config_path.exists():
            return None
        from .generate import ENV_DETECTED_FIELDS, generate_config_toml_from_app_model

        config_dict = self._parse_or_recover()
        for section, field in ENV_DETECTED_FIELDS:
            config_dict.get(section, {}).pop(field, None)
        for (section, field), stale in LEGACY_DEFAULTS.items():
            if config_dict.get(section, {}).get(field) == stale:
                config_dict[section].pop(field)
        try:
            app_config = AppConfig.model_validate(config_dict)
        except ValidationError as e:
            raise ConfigError(f"Cannot refresh '{self.config_path}':\n{e}")
        self.config_path.write_text(
            generate_config_toml_from_app_model(app_config), encoding="utf-8"
        )
        return app_config

    def load(self, update: Dict = {}, allow_setup=True) -> AppConfig:
        """
        Loads the configuration and returns a populated, validated AppConfig object.

        Args:
            update: A dictionary of CLI overrides to apply to the loaded config.

        Returns:
            An instance of AppConfig with values from the user's .toml file.

        Raises:
            ConfigError: If the configuration file contains validation or parsing errors.
        """
        if not self.config_path.exists() and allow_setup:
            return self._handle_first_run()

        config_dict = self._parse_or_recover()

        # Apply CLI overrides on top of the loaded configuration
        if update:
            for section, values in update.items():
                if section in config_dict:
                    config_dict[section].update(values)
                else:
                    config_dict[section] = values

        try:
            app_config = AppConfig.model_validate(config_dict)
            return app_config
        except ValidationError as e:
            error_message = (
                f"Configuration error in '{self.config_path}'!\n"
                f"Please correct the following issues:\n\n{e}"
            )
            raise ConfigError(error_message)
