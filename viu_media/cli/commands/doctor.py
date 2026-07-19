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
    print(f"  sixel-capable (real image previews): {_yes(sixel)}")

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
