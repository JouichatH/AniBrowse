import itertools
import textwrap
from enum import Enum
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

from pydantic.fields import ComputedFieldInfo, FieldInfo
from pydantic_core import PydanticUndefined

from ...core.config import AppConfig
from ...core.constants import APP_ASCII_ART, CLI_NAME, DISCORD_INVITE, REPO_HOME

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
# You can modify these values to customize the behavior of Viu.
# For path-based options, you can use '~' for your home directory.
""".lstrip()

CONFIG_FOOTER = f"""
# ==============================================================================
#
# HOPE YOU ENJOY {CLI_NAME} AND BE SURE TO STAR THE PROJECT ON GITHUB
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

    config_ini_content = [CONFIG_HEADER]

    for section_name, section_model in app_model:
        section_comment = section_model.model_config.get("title", "")

        config_ini_content.append(f"\n#\n# {section_comment}\n#")
        config_ini_content.append(f"[{section_name}]")

        for field_name, field_info in itertools.chain(
            section_model.model_fields.items(),
            section_model.model_computed_fields.items(),
        ):
            description = field_info.description or ""
            if description:
                wrapped_comment = textwrap.fill(
                    description,
                    width=78,
                    initial_indent="# ",
                    subsequent_indent="# ",
                )
                config_ini_content.append(f"\n{wrapped_comment}")

            field_type_comment = _get_field_type_comment(field_info)
            if field_type_comment:
                wrapped_comment = textwrap.fill(
                    field_type_comment,
                    width=78,
                    initial_indent="# ",
                    subsequent_indent="# ",
                )
                config_ini_content.append(wrapped_comment)
            if (
                hasattr(field_info, "default")
                and field_info.default != PydanticUndefined
            ):
                wrapped_comment = textwrap.fill(
                    f"Default: {field_info.default.value if isinstance(field_info.default, Enum) else field_info.default}",
                    width=78,
                    initial_indent="# ",
                    subsequent_indent="# ",
                )
                config_ini_content.append(wrapped_comment)

            field_value = getattr(section_model, field_name)
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


def _get_field_type_comment(field_info: FieldInfo | ComputedFieldInfo) -> str:
    """Generate a comment with type information for a field."""
    field_type = (
        field_info.annotation
        if isinstance(field_info, FieldInfo)
        else field_info.return_type
    )

    # Handle Literal and Enum types
    possible_values = []
    if field_type is not None:
        if isinstance(field_type, type) and issubclass(field_type, Enum):
            possible_values = [member.value for member in field_type]
        elif hasattr(field_type, "__origin__") and get_origin(field_type) is Literal:
            args = get_args(field_type)
            if args:
                possible_values = list(args)

    if possible_values:
        return f"Possible values: [ {', '.join(map(str, possible_values))} ]"

    # Handle basic types and numeric ranges
    type_name = _get_type_name(field_type)
    range_info = _get_range_info(field_info)

    if range_info:
        return f"Type: {type_name} ({range_info})"
    elif type_name:
        return f"Type: {type_name}"

    return ""


def _get_type_name(field_type: Any) -> str:
    """Get a user-friendly name for a field's type."""
    if field_type is str:
        return "string"
    if field_type is int:
        return "integer"
    if field_type is float:
        return "float"
    if field_type is bool:
        return "boolean"
    if field_type is Path:
        return "path"
    return ""


def _get_range_info(field_info: FieldInfo | ComputedFieldInfo) -> str:
    """Get a string describing the numeric range of a field."""
    constraints = {}
    if (
        isinstance(field_info, FieldInfo)
        and hasattr(field_info, "metadata")
        and field_info.metadata
    ):
        for constraint in field_info.metadata:
            constraint_type = type(constraint).__name__
            if constraint_type == "Ge" and hasattr(constraint, "ge"):
                constraints["min"] = constraint.ge
            elif constraint_type == "Le" and hasattr(constraint, "le"):
                constraints["max"] = constraint.le
            elif constraint_type == "Gt" and hasattr(constraint, "gt"):
                constraints["min"] = constraint.gt + 1
            elif constraint_type == "Lt" and hasattr(constraint, "lt"):
                constraints["max"] = constraint.lt - 1

    if constraints:
        min_val = constraints.get("min", "N/A")
        max_val = constraints.get("max", "N/A")
        return f"Range: {min_val}-{max_val}"

    return ""
