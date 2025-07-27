import configparser
from pathlib import Path
from typing import Dict

import click
from pydantic import ValidationError

from ...core.config import AppConfig
from ...core.constants import USER_CONFIG
from ...core.exceptions import ConfigError


class ConfigLoader:
    """
    Handles loading the application configuration from an .ini file.

    It ensures a default configuration exists, reads the .ini file,
    and uses Pydantic to parse and validate the data into a type-safe
    AppConfig object.
    """

    def __init__(self, config_path: Path = USER_CONFIG):
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

    def _handle_first_run(self) -> AppConfig:
        """Handles the configuration process when no config file is found."""
        click.echo(
            "[bold yellow]Welcome to FastAnime![/bold yellow] No configuration file found."
        )
        from InquirerPy import inquirer

        from .editor import InteractiveConfigEditor
        from .generate import generate_config_ini_from_app_model

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

        config_ini_content = generate_config_ini_from_app_model(app_config)
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(config_ini_content, encoding="utf-8")
            click.echo(
                f"Configuration file created at: [green]{self.config_path}[/green]"
            )
        except Exception as e:
            raise ConfigError(
                f"Could not create configuration file at {self.config_path!s}. Please check permissions. Error: {e}",
            )

        return app_config

    def load(self, update: Dict = {}) -> AppConfig:
        """
        Loads the configuration and returns a populated, validated AppConfig object.

        Returns:
            An instance of AppConfig with values from the user's .ini file.

        Raises:
            click.ClickException: If the configuration file contains validation errors.
        """
        if not self.config_path.exists():
            return self._handle_first_run()

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
        if update:
            for key in config_dict:
                if key in update:
                    config_dict[key].update(update[key])
        try:
            app_config = AppConfig.model_validate(config_dict)
            return app_config
        except ValidationError as e:
            error_message = (
                f"Configuration error in '{self.config_path}'!\n"
                f"Please correct the following issues:\n\n{e}"
            )
            raise ConfigError(error_message)
