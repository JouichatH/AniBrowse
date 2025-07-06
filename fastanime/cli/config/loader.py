import configparser
from pathlib import Path

import click
from pydantic import ValidationError

from ...core.config import AppConfig
from ...core.exceptions import ConfigError
from ..constants import USER_CONFIG_PATH
from .generate import generate_config_ini_from_app_model


class ConfigLoader:
    """
    Handles loading the application configuration from an .ini file.

    It ensures a default configuration exists, reads the .ini file,
    and uses Pydantic to parse and validate the data into a type-safe
    AppConfig object.
    """

    def __init__(self, config_path: Path = USER_CONFIG_PATH):
        """
        Initializes the loader with the path to the configuration file.

        Args:
            config_path: The path to the user's config.ini file.
        """
        self.config_path = config_path
        self.parser = configparser.ConfigParser(
            interpolation=None,
            # Allow boolean values without a corresponding value (e.g., `enabled` vs `enabled = true`)
            allow_no_value=True,
            # Behave like a dictionary, preserving case sensitivity of keys
            dict_type=dict,
        )

    def _create_default_if_not_exists(self) -> None:
        """
        Creates a default config file from the config model if it doesn't exist.
        This is the only time we write to the user's config directory.
        """
        if not self.config_path.exists():
            config_ini_content = generate_config_ini_from_app_model(
                AppConfig().model_validate({})
            )
            try:
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                self.config_path.write_text(config_ini_content, encoding="utf-8")
                click.echo(f"Created default configuration file at: {self.config_path}")
            except Exception as e:
                raise ConfigError(
                    f"Could not create default configuration file at {self.config_path!s}. Please check permissions. Error: {e}",
                )

    def load(self) -> AppConfig:
        """
        Loads the configuration and returns a populated, validated AppConfig object.

        Returns:
            An instance of AppConfig with values from the user's .ini file.

        Raises:
            click.ClickException: If the configuration file contains validation errors.
        """
        self._create_default_if_not_exists()

        try:
            self.parser.read(self.config_path, encoding="utf-8")
        except configparser.Error as e:
            raise ConfigError(
                f"Error parsing configuration file '{self.config_path}':\n{e}"
            )

        # Convert the configparser object into a nested dictionary that mirrors
        # the structure of our AppConfig Pydantic model.
        config_dict = {
            section: dict(self.parser.items(section))
            for section in self.parser.sections()
        }
        try:
            app_config = AppConfig.model_validate(config_dict)
            return app_config
        except ValidationError as e:
            error_message = (
                f"Configuration error in '{self.config_path}'!\n"
                f"Please correct the following issues:\n\n{e}"
            )
            raise ConfigError(error_message)
