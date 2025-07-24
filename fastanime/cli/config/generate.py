import textwrap
from enum import Enum
from pathlib import Path

from ...core.config import AppConfig
from ...core.constants import APP_ASCII_ART, DISCORD_INVITE, PROJECT_NAME, REPO_HOME

# The header for the config file.
config_asci = "\n".join(
    [f"# {line}" for line in APP_ASCII_ART.read_text(encoding="utf-8").split()]
)
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

CONFIG_FOOTER = f"""
# ==============================================================================
#
# HOPE YOU ENJOY {PROJECT_NAME} AND BE SURE TO STAR THE PROJECT ON GITHUB
# {REPO_HOME}
#
# Also join the discord server
# where the anime tech community lives :)
# {DISCORD_INVITE}
#
# ==============================================================================
""".lstrip()


def generate_config_ini_from_app_model(app_model: AppConfig) -> str:
    """Generate a configuration file content from a Pydantic model."""

    model_schema = AppConfig.model_json_schema(mode="serialization")
    app_model_dict = app_model.model_dump()
    config_ini_content = [CONFIG_HEADER]

    for section_name, section_dict in app_model_dict.items():
        section_ref = model_schema["properties"][section_name].get("$ref")
        if not section_ref:
            continue

        section_class_name = section_ref.split("/")[-1]
        section_schema = model_schema["$defs"][section_class_name]
        section_comment = section_schema.get("description", "")

        config_ini_content.append(f"\n#\n# {section_comment}\n#")
        config_ini_content.append(f"[{section_name}]")

        for field_name, field_value in section_dict.items():
            field_properties = section_schema.get("properties", {}).get(field_name, {})
            description = field_properties.get("description", "")

            if description:
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
            elif isinstance(field_value, Enum):
                value_str = field_value.value
            else:
                value_str = str(field_value)

            config_ini_content.append(f"{field_name} = {value_str}")

    config_ini_content.extend(["\n", CONFIG_FOOTER])
    return "\n".join(config_ini_content)
