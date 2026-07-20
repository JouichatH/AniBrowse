"""Browser-minted aaReq token capture for allanime (the "crypto treadmill").

Allanime gates its source endpoint behind a signed ``aaReq`` token whose
signing material now comes from an obfuscated, Cloudflare-Turnstile-protected
bootstrap handshake - so the token can no longer be built offline (it returns
AA_CRYPTO_STALE / AA_CRYPTO_MISSING). It CAN, however, be minted the honest
way by a real browser and then reused: the token carries no show/episode, so
ONE capture serves every episode for its validity window, and it replays fine
from plain HTTP on the same machine (verified 2026-07-20).

This module drives a LOCAL browser (Playwright, using the user's installed
Chrome when available, with a persistent profile so the Cloudflare clearance
cookie sticks across runs) to a real episode page, then reads off the browser's
OWN source request: the ``aaReq`` token, the persisted-query hash, and the
actual API host + Referer/Origin (so a host move like allanime->mkissa is
discovered automatically instead of hardcoded).

The result is cached to disk and consumed by the allanime provider. It is
entirely app-owned - no external service and no MCP - so the app captures its
own tokens with no human in the loop except the rare first-run Cloudflare
click. Lives in the (tracked) provider package, not the (gitignored, wheel-
fetched) allanime subpackage, so it ships normally.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import time
import urllib.request
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

# --- keygen extraction (the rotating decrypt key + query hash) --------------
# The response blob is encrypted with a key that rotates every few days in step
# with the aaReq token, so a browser-captured token must be paired with a key
# from the SAME rotation. We re-derive it the way the web client does; shared
# with scripts/allanime_keygen.py.
_FRONTEND_URL = "https://mkissa.to/"
_CDN_IMMUTABLE = "https://cdn.allanime.day/all/mk/_app/immutable/"
_STATIC_KEY = "Xot36i3lK3:v1"
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _BROWSER_UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="replace")


def _source_query_hash(chunk_js: str) -> Optional[str]:
    """sha256 of the episode-sources GraphQL query template in the chunk."""
    template = next(
        (
            t
            for t in re.findall(r"(\nquery\([^`]*)`", chunk_js)
            if "sourceUrls" in t and "episode(" in t
        ),
        None,
    )
    if template is None:
        return None

    def resolve(tmpl: str, depth: int = 0) -> str:
        if depth > 6:
            return tmpl
        for name in re.findall(r"\$\{([^}]+)\}", tmpl):
            if name.endswith("()"):
                fn = re.search(
                    r"\b"
                    + re.escape(name[:-2])
                    + r"\s*=\s*\w+\s*=>\s*\w+\s*\?\s*`[^`]*`\s*:\s*`([^`]*)`",
                    chunk_js,
                )
                repl = fn.group(1) if fn else ""
            else:
                var = re.search(r"\b" + re.escape(name) + r"\s*=\s*`([^`]*)`", chunk_js)
                repl = resolve(var.group(1), depth + 1) if var else ""
            tmpl = tmpl.replace("${" + name + "}", repl)
        return tmpl

    query = resolve(template)
    return None if "${" in query else hashlib.sha256(query.encode()).hexdigest()


def extract_keygen() -> Optional[dict[str, Any]]:
    """Re-derive the current {epoch, key, query_hash, static_key} from the live
    site (key = chunk mask XOR base64(partB)). None if the site can't be read."""
    try:
        html = _http_get(_FRONTEND_URL)
        m = re.search(r"window\.__aaCrypto\s*=\s*(\{.*?\})", html)
        if not m:
            return None
        aa = json.loads(m.group(1))
        part_b, epoch = aa["partB"], aa["epoch"]
        app_m = re.search(r"_app/immutable/(entry/app\.[^\"']+\.js)", html)
        if not app_m:
            return None
        app_js = _http_get(_CDN_IMMUTABLE + app_m.group(1))
        for chunk in re.findall(r"\s*[\"']\.\./(chunks/[A-Za-z0-9_\-]+\.js)[\"']", app_js):
            js = _http_get(_CDN_IMMUTABLE + chunk)
            if "__aaCrypto" not in js:
                continue
            masks = re.findall(r"[0-9a-f]{64}", js)
            if len(masks) != 1:
                continue
            key = bytes(
                a ^ b for a, b in zip(bytes.fromhex(masks[0]), base64.b64decode(part_b))
            ).hex()
            qh = _source_query_hash(js)
            if not qh:
                return None
            return {"epoch": int(epoch), "key": key, "query_hash": qh, "static_key": _STATIC_KEY}
    except Exception as e:  # noqa: BLE001 - best-effort; caller falls back
        logger.debug("keygen extraction failed: %s", e)
    return None

# Direct player pages: landing here fires the source (token) request as soon
# as the Cloudflare check clears, so it's the reliable capture path. Host-first,
# newest known host at the top; the token's actual host is still read off the
# real request, so a move to a NEW host self-heals as long as one of these
# still redirects there.
PLAYER_URLS = [
    "https://mkissa.to/anime/{show_id}/p-1-sub",
]
# Fallback for a full host move: these stable search fronts redirect to the
# current player host when an episode is opened (see _open_first_episode).
DISCOVERY_URLS = [
    "https://allmanga.to/bangumi/{show_id}",
    "https://allanime.to/bangumi/{show_id}",
]
# A perennially-present show with many episodes - a reliable capture target.
CAPTURE_SHOW_ID = "ReooPAxPMsHM4KPMY"  # One Piece
# Any request to <host>/api carrying an aaReq is a freshly-minted token.
_SOURCE_MARKER = "aaReq"
# The token's own payload buckets its timestamp to 5 min; the server honours it
# comfortably longer, but re-capturing every ~25 min keeps a wide safety margin.
DEFAULT_MAX_AGE = 25 * 60


def _cache_file() -> "Any":
    from ....core.constants import APP_CACHE_DIR

    return APP_CACHE_DIR / "allanime_token.json"


def _profile_dir() -> str:
    from ....core.constants import APP_CACHE_DIR

    d = APP_CACHE_DIR / "browser_profile"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def load_cached_token(max_age: float = DEFAULT_MAX_AGE) -> Optional[dict[str, Any]]:
    """Return the cached capture ({token, query_hash, api_host, referer,
    origin, ...}) if present and fresher than ``max_age`` seconds, else None."""
    try:
        data = json.loads(_cache_file().read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - no/broken cache just means "capture"
        return None
    if time.time() - data.get("captured_at", 0) > max_age:
        return None
    if not all(data.get(k) for k in ("token", "query_hash", "api_host")):
        return None
    return data


def invalidate_cached_token() -> None:
    """Drop the cached token (called when the server rejects it as stale)."""
    try:
        _cache_file().unlink()
    except OSError:
        pass


def playwright_available() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return False
    return True


def _user_opted_in() -> bool:
    """True once the user has captured at least once (the cache file exists,
    even if now expired) - our implicit opt-in signal for silent refreshes."""
    return _cache_file().exists()


def get_active_token(headless: bool = True) -> Optional[dict[str, Any]]:
    """Best token for the provider: fresh cache, else a silent refresh.

    Returns a capture dict or None. Never launches a browser for a user who has
    not captured at least once via ``ani-browse allanime-token`` - so nothing
    pops up unexpectedly. For opted-in users a cache miss triggers a HEADLESS
    refresh, which succeeds while the persistent profile's Cloudflare clearance
    cookie is still valid and fails quietly otherwise (provider -> nyaa).
    """
    cached = load_cached_token()
    if cached:
        return cached
    if _user_opted_in() and playwright_available():
        logger.info("allanime token expired; attempting silent browser refresh")
        return capture_token(headless=headless)
    return None


def capture_token(
    show_id: str = CAPTURE_SHOW_ID,
    headless: bool = False,
    timeout: float = 90.0,
) -> Optional[dict[str, Any]]:
    """Drive a local browser to mint and capture one aaReq token.

    Returns the capture dict (also written to the cache) or None on failure
    (Playwright missing, Cloudflare unsolved, no source request seen in time).
    Never raises - a failed capture just means the provider falls back.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.info(
            "playwright not installed; skipping allanime token capture "
            "(streaming will use the nyaa fallback). Install with: "
            "pip install playwright && playwright install chromium"
        )
        return None

    captured: dict[str, Any] = {}

    def _on_request(request: Any) -> None:
        if captured or _SOURCE_MARKER not in request.url:
            return
        try:
            headers = dict(request.headers)
        except Exception:  # noqa: BLE001 - headers best-effort
            headers = {}
        parsed = _parse_source_request(request.url, headers)
        if parsed:
            captured.update(parsed)

    try:
        with sync_playwright() as pw:
            # Prefer the user's real Chrome (real fingerprint + cookies) so
            # Cloudflare rarely challenges; fall back to bundled Chromium.
            launch_kwargs: dict[str, Any] = dict(
                user_data_dir=_profile_dir(),
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            try:
                ctx = pw.chromium.launch_persistent_context(channel="chrome", **launch_kwargs)
            except Exception:  # noqa: BLE001 - no Chrome channel -> bundled chromium
                ctx = pw.chromium.launch_persistent_context(**launch_kwargs)

            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.on("request", _on_request)

            deadline = time.monotonic() + timeout
            # Phase 1: land directly on a player page - the token fires as soon
            # as the Cloudflare check clears (auto or one user click).
            for entry in PLAYER_URLS:
                if captured:
                    break
                try:
                    page.goto(entry.format(show_id=show_id), timeout=30000)
                except Exception as e:  # noqa: BLE001 - try the next entry
                    logger.debug("token capture: player %s failed: %s", entry, e)
                    continue
                while not captured and time.monotonic() < deadline:
                    page.wait_for_timeout(500)

            # Phase 2 (only if a host move broke the direct URLs): discover the
            # current host via a stable search front + opening an episode.
            for entry in DISCOVERY_URLS:
                if captured or time.monotonic() >= deadline:
                    break
                try:
                    page.goto(entry.format(show_id=show_id), timeout=30000)
                except Exception as e:  # noqa: BLE001 - try the next entry
                    logger.debug("token capture: discovery %s failed: %s", entry, e)
                    continue
                _open_first_episode(page)
                while not captured and time.monotonic() < deadline:
                    page.wait_for_timeout(500)

            ctx.close()
    except Exception as e:  # noqa: BLE001 - capture is always best-effort
        logger.warning("allanime token capture failed: %s", e)
        return None

    if not captured:
        logger.info("allanime token capture: no source request seen (Cloudflare?)")
        return None

    # The decrypt key is NOT stored here - it rotates faster than the token and
    # is derived live at decode time (utils.fetch_keygen -> extract_keygen).
    captured["captured_at"] = time.time()
    captured["show_id"] = show_id
    try:
        _cache_file().write_text(json.dumps(captured), encoding="utf-8")
    except OSError:
        pass
    logger.info("allanime token captured from %s", captured.get("api_host"))
    return captured


def _parse_source_request(
    url: str, headers: Optional[dict[str, str]] = None
) -> Optional[dict[str, str]]:
    """Pull token + query_hash + host from a source request, or None.

    The Referer/Origin come from the request's OWN headers (the frontend page,
    e.g. mkissa.to) - NOT the API host - because the API rejects requests
    carrying the wrong Referer.
    """
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    extensions = qs.get("extensions", [None])[0]
    if not extensions:
        return None
    try:
        ext = json.loads(extensions)
    except json.JSONDecodeError:
        return None
    token = ext.get("aaReq")
    query_hash = (ext.get("persistedQuery") or {}).get("sha256Hash")
    if not token or not query_hash:
        return None
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    referer = headers.get("referer")
    origin = headers.get("origin")
    if not referer and origin:
        referer = origin.rstrip("/") + "/"
    if not referer:  # last resort - the frontend host, not the api host
        host = (parsed.hostname or "").replace("api.", "", 1)
        referer = f"{parsed.scheme}://{host}/"
    if not origin:
        origin = referer.rstrip("/")
    return {
        "token": token,
        "query_hash": query_hash,
        "api_host": f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
        "referer": referer,
        "origin": origin,
    }


def _open_first_episode(page: Any) -> None:
    """Best-effort: click into the first episode so the player loads."""
    for click_js in (
        # allmanga episode list: open the earliest page, then episode 1.
        "() => { const b=[...document.querySelectorAll('button.episodespage-indicator')]"
        ".find(x=>/^\\s*1\\s*-/.test(x.textContent||'')); if(b) b.click(); }",
        "() => new Promise(r=>setTimeout(()=>{const e=[...document.querySelectorAll("
        "'.link-7 *, .list-group-item')].find(x=>/^\\s*1\\s*$/.test(x.textContent||''));"
        " if(e) e.click(); r();}, 1200))",
    ):
        try:
            page.evaluate(click_js)
        except Exception:  # noqa: BLE001 - listener still catches the request
            pass
