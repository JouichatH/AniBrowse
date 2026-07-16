#!/usr/bin/env python3
"""Fetch the provider scrapers from the upstream viu-media PyPI wheel.

ani-browse's public repo intentionally does NOT vendor the provider scraper
code (allanime / animepahe / animeunity) — matching upstream viu-media, which
ships them only in its published wheel, not its GitHub source. This script
downloads that wheel and drops the provider packages into the installed
viu_media package so the app is fully functional.

Run it with the SAME Python that has ani-browse (viu-media) installed:
    python scripts/fetch_providers.py
The installers do this automatically after installing the app.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# Keep in step with the fork's base version (pyproject `version`).
UPSTREAM_VERSION = "3.5.0"
PROVIDERS = ["allanime", "animepahe", "animeunity"]
PKG_PREFIX = "viu_media/libs/provider/anime/"

# ---------------------------------------------------------------------------
# allanime best-first ranking patch (see ani-browse provider-ranking design).
#
# The provider scrapers are fetched from the upstream wheel and NOT vendored in
# the public repo, so fork-owned edits to them can't live as committed source.
# Instead we reproduce the one ranking edit here as an idempotent, marker-guarded,
# version-pinned text patch applied right after fetch. Each provider is expected
# to yield servers best-first with honest quality; allanime's raw `sourceUrls`
# order is arbitrary, so we dedupe by sourceName and sort by allanime's own
# `priority` float (descending). This makes `all_servers[0]` and
# launch-on-first-success land on the best extractable source and drops the
# duplicate extraction the raw list caused.
#
# The patch is a plain string replacement anchored on the exact upstream 3.5.0
# body of `episode_streams`; if that body ever changes (version bump) the anchor
# won't match and we skip rather than corrupt the file — bump UPSTREAM_VERSION
# and re-derive the anchor at the same time.
RANKING_PATCH_MARKER = "# [ani-browse:ranking-patch]"

_RANKING_ANCHOR = """\
        for source in sources:
            if server := extract_server(self.client, params.episode, episode, source):
                yield server"""

_RANKING_REPLACEMENT = """\
        # [ani-browse:ranking-patch] Best-first contract: dedupe sources by
        # sourceName and yield highest-priority first (allanime's own `priority`
        # float), so all_servers[0] / launch-on-first-success lands on the best
        # extractable source instead of arbitrary raw payload order, and the
        # duplicate extraction the raw list caused is dropped.
        _seen: set[str] = set()
        _ranked: list = []
        for source in sources:
            _name = source.get("sourceName")
            if _name in _seen:
                continue
            _seen.add(_name)
            _ranked.append(source)
        _ranked.sort(key=lambda s: s.get("priority") or 0.0, reverse=True)

        for source in _ranked:
            if server := extract_server(self.client, params.episode, episode, source):
                yield server"""


def apply_ranking_patch(text: str) -> tuple[str, str]:
    """Apply the allanime ranking patch to a provider.py's source text.

    Pure and idempotent. Returns ``(new_text, status)`` where status is:
      - ``"already"``  the marker is present; text returned unchanged.
      - ``"skipped"``  the expected upstream anchor was not found (unknown shape);
                        text returned unchanged.
      - ``"patched"``  the anchor was replaced with the ranking block.
    """
    if RANKING_PATCH_MARKER in text:
        return text, "already"
    if _RANKING_ANCHOR not in text:
        return text, "skipped"
    return text.replace(_RANKING_ANCHOR, _RANKING_REPLACEMENT, 1), "patched"


def _patch_allanime_ranking(dst: Path) -> None:
    """Idempotently patch the fetched allanime provider for best-first ranking."""
    provider = dst / "allanime" / "provider.py"
    if not provider.exists():
        return
    original = provider.read_text(encoding="utf-8")
    new_text, status = apply_ranking_patch(original)
    if status == "patched":
        provider.write_text(new_text, encoding="utf-8")
        print("  patched allanime provider: best-first ranking applied")
    elif status == "already":
        print("  allanime ranking patch already present — nothing to do")
    else:  # skipped
        print(
            "  warning: allanime episode_streams did not match the pinned "
            f"viu-media=={UPSTREAM_VERSION} shape; ranking patch NOT applied.",
            file=sys.stderr,
        )


def _target_dir() -> Path:
    """The installed viu_media provider dir (works for editable + regular installs)."""
    import viu_media.libs.provider.anime as anime_pkg

    return Path(anime_pkg.__path__[0])


def main() -> int:
    try:
        dst = _target_dir()
    except Exception as e:  # noqa: BLE001
        print(f"error: could not locate the installed viu_media package ({e}).", file=sys.stderr)
        print("Run this with the Python that has ani-browse installed.", file=sys.stderr)
        return 1

    missing = [p for p in PROVIDERS if not (dst / p / "provider.py").exists()]
    if not missing:
        print(f"Providers already present in {dst} — nothing to fetch.")
        # Still (idempotently) ensure the ranking patch is applied to a
        # pre-existing install.
        _patch_allanime_ranking(dst)
        return 0

    print(f"Fetching providers {missing} from viu-media=={UPSTREAM_VERSION} ...")
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        try:
            subprocess.run(
                [
                    sys.executable, "-m", "pip", "download",
                    f"viu-media=={UPSTREAM_VERSION}",
                    "--no-deps", "--only-binary", ":all:", "-d", str(tmpdir),
                ],
                check=True,
            )
        except subprocess.CalledProcessError:
            print("error: failed to download the viu-media wheel.", file=sys.stderr)
            return 1

        wheels = list(tmpdir.glob("viu_media-*.whl")) or list(tmpdir.glob("viu*.whl"))
        if not wheels:
            print("error: no wheel downloaded.", file=sys.stderr)
            return 1

        with zipfile.ZipFile(wheels[0]) as zf:
            names = zf.namelist()
            for prov in PROVIDERS:
                prefix = f"{PKG_PREFIX}{prov}/"
                members = [n for n in names if n.startswith(prefix) and not n.endswith("/")]
                if not members:
                    print(f"  warning: {prov} not found in wheel", file=sys.stderr)
                    continue
                for n in members:
                    out = dst / n[len(PKG_PREFIX):]
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(n) as src, open(out, "wb") as fh:
                        shutil.copyfileobj(src, fh)
                print(f"  installed provider: {prov}")

    _patch_allanime_ranking(dst)
    print(f"Done. Providers installed into {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
