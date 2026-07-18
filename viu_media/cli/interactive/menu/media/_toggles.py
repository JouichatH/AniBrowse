"""Shared preference toggles, persisted to config.toml.

The Toggle rows (auto-next, opening/ending skip, continue-from-history,
translation type, auto-select) are durable preferences, not per-session
experiments - flipping one should survive an app restart. Only the toggled
field is merged into the on-disk config: deliberately session-scoped state
(e.g. a quality picked for one show) stays in memory.
"""

import logging
import os
from typing import Literal

logger = logging.getLogger(__name__)

ToggleKey = Literal[
    "AUTO_ANIME",
    "AUTO_EPISODE",
    "OPENING_SKIP",
    "ENDING_SKIP",
    "CONTINUE_FROM_HISTORY",
    "TRANSLATION_TYPE",
]

#: toggle key -> (config section, field name)
_FIELDS = {
    "AUTO_ANIME": ("general", "auto_select_anime_result"),
    "AUTO_EPISODE": ("stream", "auto_next"),
    "OPENING_SKIP": ("stream", "opening_skip"),
    "ENDING_SKIP": ("stream", "ending_skip"),
    "CONTINUE_FROM_HISTORY": ("stream", "continue_from_watch_history"),
    "TRANSLATION_TYPE": ("stream", "translation_type"),
}


def apply_toggle(ctx, key: ToggleKey) -> None:
    """Flip the preference in the live config and persist it to config.toml."""
    config = ctx.config
    section_name, field = _FIELDS[key]
    section = getattr(config, section_name)
    if key == "TRANSLATION_TYPE":
        new_value = "sub" if config.stream.translation_type == "dub" else "dub"
    else:
        new_value = not getattr(section, field)
    setattr(section, field, new_value)
    _persist_field(ctx, section_name, field, new_value)


def _persist_field(ctx, section_name: str, field: str, value) -> None:
    """Merge one field into the on-disk config (best-effort - a read-only
    filesystem must not break the in-session toggle)."""
    try:
        from .....core.constants import USER_CONFIG
        from ....config.generate import generate_config_toml_from_app_model
        from ....config.loader import ConfigLoader

        disk = ConfigLoader(config_path=USER_CONFIG).load(allow_setup=False)
        setattr(getattr(disk, section_name), field, value)
        text = generate_config_toml_from_app_model(disk)
        tmp = USER_CONFIG.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, USER_CONFIG)
    except Exception:
        logger.exception(
            "could not persist %s.%s to config.toml", section_name, field
        )
        ctx.feedback.warning(
            "Preference applied for this session, but saving it to the config "
            "file failed (see log)."
        )
