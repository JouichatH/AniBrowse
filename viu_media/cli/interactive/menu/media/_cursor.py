"""Per-menu cursor memory.

Menus are re-entered constantly - after a toggle (RELOAD), after backing out of
a child menu, after an error - and a plain ``selector.choose`` puts the cursor
back on the first row every time. That makes flipping two toggles, or working
down a long list, needlessly painful. ``remembered_choose`` records which row
was picked per menu key and restores the cursor there on the next entry
(via ``start_index``, which the fzf selector maps to ``--bind start:pos`` and
other selectors ignore).

Index-based on purpose: toggle labels change ("Current: True" -> "False") but
keep their position, so remembering the index survives label churn.
"""

from typing import Dict, List, Optional

_last_index: Dict[str, int] = {}


def remembered_choose(
    selector,
    menu_key: str,
    prompt: str,
    choices: List[str],
    **kwargs,
) -> Optional[str]:
    """``selector.choose`` with the cursor restored to the last pick for
    ``menu_key`` (and the new pick recorded)."""
    index = _last_index.get(menu_key)
    if index is not None and not (0 <= index < len(choices)):
        index = None
    choice = selector.choose(
        prompt=prompt, choices=choices, start_index=index, **kwargs
    )
    if choice is not None and choice in choices:
        _last_index[menu_key] = choices.index(choice)
    return choice


def forget(menu_key: str) -> None:
    _last_index.pop(menu_key, None)
