#!/usr/bin/env python3
"""Regenerate the allanime handshake patch in scripts/fetch_providers.py.

The handshake patch turns the pristine upstream-wheel allanime files into the
fork's fixed copies. Anchors are hand-chosen stable slices of the upstream
3.5.0 text; replacements are extracted from the CURRENT local (git-ignored)
files, so the patched result is byte-identical to the development copy by
construction. Run this after every treadmill edit to the local allanime files:

    python dev/regen_handshake_patch.py

It rewrites the _HANDSHAKE_EDITS dict between the GENERATED markers in
scripts/fetch_providers.py, then verifies wheel+patch == local for all three
files (downloads the wheel on first run, caches it next to this script).
"""

from __future__ import annotations

import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LOCAL = REPO / "viu_media" / "libs" / "provider" / "anime" / "allanime"
FETCH = REPO / "scripts" / "fetch_providers.py"
WHEEL_CACHE = Path(__file__).resolve().parent / ".wheel_allanime"
UPSTREAM_VERSION = "3.5.0"

BEGIN = "# --- BEGIN GENERATED HANDSHAKE EDITS (dev/regen_handshake_patch.py) ---"
END = "# --- END GENERATED HANDSHAKE EDITS ---"


def wheel_files() -> dict[str, str]:
    if WHEEL_CACHE.exists():
        return {p.name: p.read_text(encoding="utf-8") for p in WHEEL_CACHE.glob("*.py")}
    meta = json.load(
        urllib.request.urlopen(
            f"https://pypi.org/pypi/viu-media/{UPSTREAM_VERSION}/json", timeout=30
        )
    )
    url = next(u["url"] for u in meta["urls"] if u["packagetype"] == "bdist_wheel")
    data = urllib.request.urlopen(url, timeout=120).read()
    zf = zipfile.ZipFile(io.BytesIO(data))
    WHEEL_CACHE.mkdir(exist_ok=True)
    out: dict[str, str] = {}
    prefix = "viu_media/libs/provider/anime/allanime/"
    for n in zf.namelist():
        if n.startswith(prefix) and n.endswith(".py") and "/" not in n[len(prefix):]:
            text = zf.read(n).decode("utf-8")
            (WHEEL_CACHE / n.split("/")[-1]).write_text(text, encoding="utf-8", newline="")
            out[n.split("/")[-1]] = text
    return out


def local_files() -> dict[str, str]:
    # Normalize CRLF (git-bash/Windows editors) to LF to match wheel text.
    return {
        name: (LOCAL / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        for name in ("constants.py", "utils.py", "provider.py")
    }


def slice_between(text: str, start: str, end: str, include_end: bool) -> str:
    i = text.index(start)
    j = text.index(end, i)
    return text[i : j + (len(end) if include_end else 0)]


def build_edits(wheel: dict[str, str], local: dict[str, str]) -> dict[str, list[tuple[str, str]]]:
    """(anchor, replacement) pairs per file.

    Anchors are exact upstream-3.5.0 slices; replacements are the local text
    that must stand in their place.
    """
    w_utils, l_utils = wheel["utils.py"], local["utils.py"]
    w_prov, l_prov = wheel["provider.py"], local["provider.py"]
    l_const = local["constants.py"]

    # constants.py: seed line + following blank -> deprecation note + keygen block
    const_anchor = 'TOBEPARSED_DECRYPTION_SEED = "Xot36i3lK3:v1"\n\n# search constants'
    const_repl = slice_between(l_const, "# Legacy seed:", "# search constants", True)

    # utils.py
    utils_import_anchor = slice_between(
        w_utils, "import logging", "from itertools import cycle", True
    )
    utils_import_repl = slice_between(
        l_utils, "import logging", "from itertools import cycle", True
    )
    utils_body_anchor = slice_between(
        w_utils,
        "from Cryptodome.Cipher import AES",
        "# Dictionary to map hex values to characters",
        True,
    )
    utils_body_repl = slice_between(
        l_utils,
        "from Cryptodome.Cipher import AES",
        "# Dictionary to map hex values to characters",
        True,
    )
    decode_anchor = slice_between(
        w_utils, "def decode_tobeparsed", "\n\n\ndef decode_hex_string", False
    )
    decode_repl = slice_between(
        l_utils, "def decode_tobeparsed", "\n\n\ndef decode_hex_string", False
    )

    # provider.py
    prov_import_anchor = slice_between(w_prov, "from .constants import (", ")\n", True)
    prov_import_repl = slice_between(l_prov, "from .constants import (", ")\n", True)
    # One wide slice from the first patched method through the last covers every
    # body change (decode comment, new _persisted_episode_query, rewritten
    # _get_episode_payload) as a single anchored replacement.
    payload_terminator = "return self._extract_episode_from_payload(episode_response.json())"
    prov_body_anchor = slice_between(
        w_prov, "    def _extract_episode_from_payload", payload_terminator, True
    )
    prov_body_repl = slice_between(
        l_prov, "    def _extract_episode_from_payload", payload_terminator, True
    )

    return {
        "constants.py": [(const_anchor, const_repl)],
        "utils.py": [
            (utils_import_anchor, utils_import_repl),
            (utils_body_anchor, utils_body_repl),
            (decode_anchor, decode_repl),
        ],
        "provider.py": [
            (prov_import_anchor, prov_import_repl),
            (
                "from .utils import decode_tobeparsed\n",
                "from .utils import decode_tobeparsed, fetch_keygen, get_aa_req\n",
            ),
            (prov_body_anchor, prov_body_repl),
        ],
    }


def emit_dict(edits: dict[str, list[tuple[str, str]]]) -> str:
    lines = ["_HANDSHAKE_EDITS: dict[str, list[tuple[str, str]]] = {"]
    for fname, pairs in edits.items():
        lines.append(f"    {fname!r}: [")
        for anchor, repl in pairs:
            lines.append(f"        ({anchor!r},")
            lines.append(f"         {repl!r}),")
        lines.append("    ],")
    lines.append("}")
    return "\n".join(lines)


def main() -> int:
    wheel = wheel_files()
    local = local_files()
    edits = build_edits(wheel, local)

    fetch_text = FETCH.read_text(encoding="utf-8")
    i = fetch_text.index(BEGIN) + len(BEGIN)
    j = fetch_text.index(END)
    fetch_text = fetch_text[:i] + "\n" + emit_dict(edits) + "\n" + fetch_text[j:]
    FETCH.write_text(fetch_text, encoding="utf-8")

    # Verify: wheel + patch must equal the local files byte-for-byte.
    import importlib.util

    spec = importlib.util.spec_from_file_location("fetch_providers", FETCH)
    assert spec and spec.loader
    fp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fp)
    ok = True
    for name in ("constants.py", "utils.py", "provider.py"):
        patched, status = fp.apply_handshake_patch(name, wheel[name])
        if name == "provider.py":
            patched, _ = fp.apply_ranking_patch(patched)
        if status != "patched" or patched != local[name]:
            print(f"MISMATCH {name}: status={status}", file=sys.stderr)
            ok = False
        else:
            print(f"verified {name}: wheel+patch == local")
    if not ok:
        return 1
    print(f"OK - regenerated handshake edits in {FETCH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
