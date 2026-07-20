"""Doctor command: diagnose a machine's install in one shot.

Prints everything that varies between machines and explains the classic
"works on my machine" install symptoms - terminal capability detection
(icons / preview / image renderer), external tool availability, provider
scrapers and their fork patches, and where the config diverges from what
live detection would pick right now.
"""

import importlib
import os
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich import print
from rich.table import Table

if TYPE_CHECKING:
    from ...core.config import AppConfig

# Env markers a modern Windows console host sets (see detect.is_legacy_windows_console).
_HOST_MARKERS = (
    "WT_SESSION",
    "TERM_PROGRAM",
    "ConEmuANSI",
    "ALACRITTY_WINDOW_ID",
    "WEZTERM_PANE",
    "TERM",
    "KITTY_WINDOW_ID",
)

_TOOLS = ("fzf", "chafa", "mpv", "webtorrent", "node", "uv")

# Fetched (non-vendored) providers and the substrings that prove each fork
# patch landed in the installed copy (see scripts/fetch_providers.py).
_FETCHED_PROVIDERS = ("allanime", "animepahe", "animeunity")
_ALLANIME_CHECKS = {
    "aaReq handshake fix": "get_aa_req",
    "best-first ranking patch": "[ani-browse:ranking-patch]",
}


def _yes(ok: bool) -> str:
    return "[green]yes[/]" if ok else "[red]NO[/]"


def _windows_terminal_version() -> str:
    """Installed Windows Terminal package version, or '' if undetermined."""
    import subprocess

    try:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-AppxPackage Microsoft.WindowsTerminal*).Version",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()
        return out.splitlines()[0].strip() if out else ""
    except Exception:  # noqa: BLE001 - diagnostic only, never fail doctor
        return ""


@click.command(
    help="Diagnose this machine's ani-browse install (terminal, tools, providers, config).",
    short_help="Diagnose this install",
)
@click.pass_obj
def doctor(config: "AppConfig") -> None:
    from ...core.constants import USER_CONFIG
    from ...core.utils import detect

    # --- Terminal ----------------------------------------------------------
    print("\n[bold]Terminal[/]")
    table = Table(show_header=False, box=None, pad_edge=False)
    for marker in _HOST_MARKERS:
        value = os.environ.get(marker)
        if value:
            table.add_row(f"  {marker}", f"[green]{value}[/]")
        else:
            table.add_row(f"  {marker}", "[dim]unset[/]")
    print(table)
    legacy = detect.is_legacy_windows_console()
    sixel = detect.is_sixel_capable_terminal()
    if legacy:
        print("  legacy conhost: [red]YES - icons auto-disabled, use Windows Terminal[/]")
    else:
        print("  legacy conhost: [green]no[/]")
    print(f"  sixel-capable per env detection: {_yes(sixel)}")

    # Env detection can't see the terminal VERSION: Windows Terminal renders
    # sixel only from 1.22, but sets WT_SESSION on every version. Report the
    # installed version and emit a real sixel block so the human can verify.
    if sys.platform == "win32" and os.environ.get("WT_SESSION"):
        wt_version = _windows_terminal_version()
        if wt_version:
            print(f"  Windows Terminal version: {wt_version}", end="")
            major_minor = wt_version.split(".")[:2]
            try:
                too_old = (int(major_minor[0]), int(major_minor[1])) < (1, 22)
            except (ValueError, IndexError):
                too_old = False
            if too_old:
                print(
                    "  [red](sixel needs >= 1.22 - cover images will be BLANK; "
                    "update via 'winget upgrade Microsoft.WindowsTerminal' or the "
                    "Microsoft Store)[/]"
                )
            else:
                print("  [green](>= 1.22, sixel-era)[/]")
        else:
            print("  Windows Terminal version: [dim]could not determine[/]")
    if sixel and sys.stdout.isatty():
        # 48x12px block, colour-banded. Raw escape bytes on purpose - rich
        # would mangle them. TTY-only: piped output would just show garbage.
        sys.stdout.flush()
        sys.stdout.write(
            "\x1bPq"
            "#0;2;85;30;30#0!48~-"
            "#1;2;30;70;35#1!48~"
            "\x1b\\\n"
        )
        sys.stdout.flush()
        print(
            "  sixel self-test: a small red/green block should appear just "
            "above this line."
        )
        print(
            "  [dim]No block -> this terminal ignores sixel; either update it or "
            'set image_renderer = "chafa" in config.toml for symbol-art covers.[/]'
        )

    # --- External tools ----------------------------------------------------
    print("\n[bold]External tools[/]")
    for tool in _TOOLS:
        path = shutil.which(tool)
        if path:
            print(f"  [green]OK[/]  {tool:<11} {path}")
        else:
            print(f"  [red]MISSING[/]  {tool:<11} (not on PATH)")

    # --- Providers ---------------------------------------------------------
    print("\n[bold]Provider scrapers[/] [dim](fetched from the viu-media wheel at install)[/]")
    import viu_media.libs.provider.anime as anime_pkg

    providers_dir = Path(anime_pkg.__path__[0])
    all_present = True
    for name in _FETCHED_PROVIDERS:
        present = (providers_dir / name / "provider.py").exists()
        all_present &= present
        print(f"  {name:<11} present: {_yes(present)}")
    if not all_present:
        print(
            "  [yellow]Fix: run[/]  python scripts/fetch_providers.py  "
            "[yellow]with the app's Python (the installer does this).[/]"
        )

    allanime_py = providers_dir / "allanime" / "provider.py"
    if allanime_py.exists():
        text = allanime_py.read_text(encoding="utf-8")
        utils_text = (providers_dir / "allanime" / "utils.py").read_text(
            encoding="utf-8"
        )
        for label, needle in _ALLANIME_CHECKS.items():
            ok = needle in text or needle in utils_text
            print(f"  allanime {label}: {_yes(ok)}")
            if not ok and "handshake" in label:
                print(
                    "    [red]Without this, allanime returns AA_CRYPTO_MISSING -> "
                    "0 servers -> every play silently falls back to nyaa.[/]"
                )
                print(
                    "    [yellow]Fix: re-run the installer or[/] "
                    "python scripts/fetch_providers.py"
                )
        try:
            importlib.import_module("viu_media.libs.provider.anime.allanime.provider")
            print(f"  allanime importable: {_yes(True)}")
        except Exception as e:  # noqa: BLE001 - diagnostic, report anything
            print(f"  allanime importable: {_yes(False)} ({e})")

    # --- Config vs live detection ------------------------------------------
    print("\n[bold]Config[/]")
    print(f"  file: {USER_CONFIG} (exists: {_yes(USER_CONFIG.exists())})")
    from ...core.config import defaults

    detected = {
        "selector": defaults.GENERAL_SELECTOR(),
        "preview": defaults.GENERAL_PREVIEW(),
        "image_renderer": defaults.GENERAL_IMAGE_RENDERER(),
    }
    for field, live in detected.items():
        current = getattr(config.general, field)
        if current == live:
            print(f"  {field:<15} = {current}  [dim](matches live detection)[/]")
        else:
            print(
                f"  {field:<15} = {current}  [yellow](live detection would pick "
                f"'{live}' - a frozen or pinned value; delete/comment the line in "
                f"config.toml to re-detect each launch)[/]"
            )
    icons_effective = config.general.icons and not legacy
    print(
        f"  icons           = {config.general.icons}  "
        f"(effective this session: {icons_effective})"
    )

    print(
        f"\n  python: {sys.version.split()[0]}  ({sys.executable})"
    )
