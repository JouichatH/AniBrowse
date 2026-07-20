"""`ani-browse allanime-token` - authorize allanime streaming via the browser.

Allanime gates its streams behind a token only a real browser can mint (see
libs/provider/anime/token_capture). This command opens a browser window to an
episode page; the user clears the one-time Cloudflare check, and the token is
captured and cached. Normal streaming then uses it silently (and auto-refreshes
headlessly while the browser profile's clearance cookie lasts). Without it,
allanime falls back to nyaa torrents.
"""

import click
from rich import print


@click.command(
    name="allanime-token",
    help="Authorize allanime streaming by capturing a token in your browser.",
    short_help="Authorize allanime (browser)",
)
@click.option("--headless", is_flag=True, help="Run without a visible window (needs a warm profile).")
@click.option("--timeout", default=180, show_default=True, help="Seconds to wait for the capture.")
def allanime_token(headless: bool, timeout: int) -> None:
    from ...libs.provider.anime import token_capture

    if not token_capture.playwright_available():
        print(
            "[red]Playwright is not installed.[/] Install it, then re-run:\n"
            "  [cyan]pip install playwright[/]\n"
            "  [cyan]playwright install chromium[/]"
        )
        raise SystemExit(1)

    print(
        "[cyan]Opening a browser to allanime…[/] If a Cloudflare "
        "[bold]'Verify you are human'[/] check appears, click it. "
        "The window closes itself once the token is captured."
    )
    result = token_capture.capture_token(headless=headless, timeout=float(timeout))
    if result:
        # Plain ASCII only - the classic Windows console (cp1252) can't encode
        # symbols like a check mark and rich raises UnicodeEncodeError there.
        print(
            f"[green]allanime authorized.[/] Token captured from "
            f"[dim]{result.get('api_host')}[/]. Streaming will use it automatically."
        )
    else:
        print(
            "[yellow]Could not capture a token.[/] The Cloudflare check may not "
            "have been solved in time. Re-run [cyan]ani-browse allanime-token[/] "
            "and click the checkbox. Meanwhile, nyaa torrents remain available."
        )
        raise SystemExit(1)
