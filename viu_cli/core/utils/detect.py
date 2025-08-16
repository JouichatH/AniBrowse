import os
import re
import shutil
import sys


def is_running_in_termux():
    # Check environment variables
    if os.environ.get("TERMUX_VERSION") is not None:
        return True

    # Check Python installation path
    if sys.prefix.startswith("/data/data/com.termux/files/usr"):
        return True

    # Check for Termux-specific binary
    if os.path.exists("/data/data/com.termux/files/usr/bin/termux-info"):
        return True

    return False


def is_bash_script(text: str) -> bool:
    # Normalize line endings
    text = text.strip()

    # Check for shebang at the top
    if text.startswith("#!/bin/bash") or text.startswith("#!/usr/bin/env bash"):
        return True

    # Look for common bash syntax/keywords
    bash_keywords = [
        r"\becho\b",
        r"\bfi\b",
        r"\bthen\b",
        r"\bfunction\b",
        r"\bfor\b",
        r"\bwhile\b",
        r"\bdone\b",
        r"\bcase\b",
        r"\besac\b",
        r"\$\(",
        r"\[\[",
        r"\]\]",
        r";;",
    ]

    # Score based on matches
    matches = sum(bool(re.search(pattern, text)) for pattern in bash_keywords)
    return matches >= 2


def is_running_kitty_terminal() -> bool:
    return True if os.environ.get("KITTY_WINDOW_ID") else False


def has_fzf() -> bool:
    return True if shutil.which("fzf") else False
