import configparser
import textwrap
from pathlib import Path

import click
from pydantic import ValidationError

from ..constants import USER_CONFIG_PATH
from .model import AppConfig
from ...core.exceptions import ConfigError


from ..constants import ASCII_ART


# The header for the config file.
config_asci = "\n".join([f"# {line}" for line in ASCII_ART.split()])
CONFIG_HEADER = f"""
# ==============================================================================
# 
{config_asci}
#
# ==============================================================================
# This file was auto-generated from the application's configuration model.
# You can modify these values to customize the behavior of FastAnime.
# For path-based options, you can use '~' for your home directory.
""".lstrip()


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
            default_config = AppConfig.model_validate({})

            model_schema = AppConfig.model_json_schema()

            config_ini_content = [CONFIG_HEADER]

            for section_name, section_model in default_config:
                section_class_name = model_schema["properties"][section_name][
                    "$ref"
                ].split("/")[-1]
                section_comment = model_schema["$defs"][section_class_name][
                    "description"
                ]
                config_ini_content.append(f"\n#\n# {section_comment}\n#")
                config_ini_content.append(f"[{section_name}]")

                for field_name, field_value in section_model:
                    description = model_schema["$defs"][section_class_name][
                        "properties"
                    ][field_name].get("description", "")

                    if description:
                        # Wrap long comments for better readability in the .ini file
                        wrapped_comment = textwrap.fill(
                            description,
                            width=78,
                            initial_indent="# ",
                            subsequent_indent="# ",
                        )
                        config_ini_content.append(f"\n{wrapped_comment}")

                    if isinstance(field_value, bool):
                        value_str = str(field_value).lower()
                    elif isinstance(field_value, Path):
                        value_str = str(field_value)
                    elif field_value is None:
                        value_str = ""
                    else:
                        value_str = str(field_value)

                    config_ini_content.append(f"{field_name} = {value_str}")
            try:
                final_output = "\n".join(config_ini_content)
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                self.config_path.write_text(final_output, encoding="utf-8")
                click.echo(f"Created default configuration file at: {self.config_path}")
            except Exception as e:
                raise ConfigError(
                    f"Could not create default configuration file at {str(self.config_path)}. Please check permissions. Error: {e}",
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
