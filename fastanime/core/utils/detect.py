import os
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
