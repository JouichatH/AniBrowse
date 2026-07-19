"""Prompts nested inside a menu action ("pick a status", "pick a server"...).

A menu's own top-level selector may let ``NavigationAbort`` (Esc) propagate:
the session loop answers it with BACK, popping that menu - there Esc means
"leave this page". A prompt spawned *inside* one of the menu's actions must
not do that: the abort would pop the menu that spawned the prompt, so Esc on
e.g. "Select list status" skipped past the actions menu straight to the
results page. In a nested prompt Esc means "cancel this action": catch the
abort and report "nothing chosen" so the caller reloads its own menu.
"""

from typing import Optional

from .....core.exceptions import NavigationAbort


def sub_choose(selector, prompt: str, choices: list, **kwargs) -> Optional[str]:
    """``selector.choose`` for a nested prompt: Esc -> None, never an abort."""
    try:
        return selector.choose(prompt, choices, **kwargs)
    except NavigationAbort:
        return None


def sub_choose_multiple(selector, prompt: str, choices: list, **kwargs) -> list:
    """``selector.choose_multiple`` for a nested prompt: Esc -> empty list."""
    try:
        return selector.choose_multiple(prompt, choices, **kwargs)
    except NavigationAbort:
        return []
