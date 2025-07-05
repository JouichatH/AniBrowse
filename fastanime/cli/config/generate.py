import textwrap
from pathlib import Path

from ..constants import APP_ASCII_ART
from .model import AppConfig

# The header for the config file.
config_asci = "\n".join([f"# {line}" for line in APP_ASCII_ART.split()])
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


def generate_config_ini_from_app_model(app_model: AppConfig) -> str:
    """Generate a configuration file content from a Pydantic model."""

    model_schema = AppConfig.model_json_schema()

    config_ini_content = [CONFIG_HEADER]

    for section_name, section_model in app_model:
        section_class_name = model_schema["properties"][section_name]["$ref"].split(
            "/"
        )[-1]
        section_comment = model_schema["$defs"][section_class_name]["description"]
        config_ini_content.append(f"\n#\n# {section_comment}\n#")
        config_ini_content.append(f"[{section_name}]")

        for field_name, field_value in section_model:
            description = model_schema["$defs"][section_class_name]["properties"][
                field_name
            ].get("description", "")

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
    return "\n".join(config_ini_content)
