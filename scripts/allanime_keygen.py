#!/usr/bin/env python3
"""Extract allanime's current aaReq crypto values from the live site.

The allanime source endpoint signs requests with rotating secrets (the
"crypto treadmill"): an epoch counter, an AES key, and the sha256 hash of the
episode-sources GraphQL query. This script re-derives all three the same way
the official web client does (recipe mirrors sdaqo/anipy-cli's keygen):

  1. The frontend page inlines ``window.__aaCrypto`` = {partB, epoch, ...}.
  2. The page's app bundle imports a crypto chunk holding a lone 64-char hex
     "mask"; the AES key is mask XOR base64decode(partB).
  3. The same chunk holds the sources GraphQL query as a template literal;
     resolving its interpolations and hashing gives query_hash.

Writes keygen/allanime.json (the file installs fetch at runtime). Run it
whenever allanime rotates (AA_CRYPTO_STALE in the app log):
    python scripts/allanime_keygen.py
The fresh-values commit heals every install on its next launch - no code
changes needed.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

FRONTEND_URL = "https://mkissa.to/"
CDN_IMMUTABLE = "https://cdn.allanime.day/all/mk/_app/immutable/"
STATIC_KEY = "Xot36i3lK3:v1"
# The request/token must use the STABLE classic persisted-query hash; the live
# JS advertises a per-client rotating hash that the API rejects with
# PersistedQueryNotFound (ani-cli #1801). We pin it and ignore the extracted one.
PINNED_QUERY_HASH = "d405d0edd690624b66baba3068e0edc3ac90f1597d898a1ec8db4e5c43c00fec"
# buildId signed into the aaReq + sent as x-build-id. Rotates occasionally
# (41 -> 44 -> 50); bump in step with ani-cli's fix branch when it changes.
BUILD_ID = "50"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
OUT_FILE = Path(__file__).resolve().parents[1] / "keygen" / "allanime.json"


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="replace")


def derive_key(mask_hex: str, part_b: str) -> str:
    return bytes(
        a ^ b for a, b in zip(bytes.fromhex(mask_hex), base64.b64decode(part_b))
    ).hex()


def source_query_hash(chunk_js: str) -> str | None:
    """sha256 of the episode-sources GraphQL query template in the chunk.

    The query is a template literal interpolating fragments (``${name}``) and
    a no-arg helper call (``${name()}`` - its else-branch literal applies).
    Returns None when the template can't be fully resolved.
    """
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
    if "${" in query:
        return None
    return hashlib.sha256(query.encode()).hexdigest()


def fetch() -> dict:
    html = _get(FRONTEND_URL)
    m = re.search(r"window\.__aaCrypto\s*=\s*(\{.*?\})", html)
    if not m:
        raise RuntimeError(
            "window.__aaCrypto not found - Cloudflare challenge or site change. "
            "Try from another network (the fresh-install CI runner works)."
        )
    aa = json.loads(m.group(1))
    part_b, epoch = aa["partB"], aa["epoch"]

    app_m = re.search(r"_app/immutable/(entry/app\.[^\"']+\.js)", html)
    if not app_m:
        raise RuntimeError("could not find the app bundle in the frontend HTML")
    app_js = _get(CDN_IMMUTABLE + app_m.group(1))
    imports = re.findall(r"\s*[\"']\.\./(chunks/[A-Za-z0-9_\-]+\.js)[\"']", app_js)
    for chunk in imports:
        js = _get(CDN_IMMUTABLE + chunk)
        if "__aaCrypto" not in js:
            continue
        masks = re.findall(r"[0-9a-f]{64}", js)
        if len(masks) != 1:
            continue
        # query_hash is pinned (not extracted): the extracted rotating hash is
        # rejected by the API; only the classic PINNED_QUERY_HASH is accepted.
        return {
            "epoch": int(epoch),
            "key": derive_key(masks[0], part_b),
            "query_hash": PINNED_QUERY_HASH,
            "build_id": BUILD_ID,
            "static_key": STATIC_KEY,
        }
    raise RuntimeError("no crypto chunk with a single 64-hex mask found")


def main() -> int:
    try:
        keygen = fetch()
    except Exception as e:  # noqa: BLE001 - single actionable failure point
        print(f"keygen extraction failed: {e}", file=sys.stderr)
        return 1
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(keygen) + "\n", encoding="utf-8")
    print(f"wrote {OUT_FILE}:")
    print(json.dumps(keygen))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
