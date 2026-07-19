"""Legacy-conhost detection: icons auto-disable where emoji can't render."""

import sys

import pytest

from viu_media.core.utils.detect import is_legacy_windows_console


def test_never_legacy_off_windows_or_in_modern_hosts():
    if sys.platform != "win32":
        # Non-Windows platforms are never "legacy console", whatever the env.
        assert is_legacy_windows_console({}) is False
    else:
        for marker in ("WT_SESSION", "TERM_PROGRAM", "ConEmuANSI"):
            assert is_legacy_windows_console({marker: "1"}) is False


@pytest.mark.skipif(sys.platform != "win32", reason="conhost is Windows-only")
def test_bare_env_on_windows_is_legacy_console():
    assert is_legacy_windows_console({}) is True
    # Empty marker values don't count as a modern host.
    assert is_legacy_windows_console({"WT_SESSION": ""}) is True
