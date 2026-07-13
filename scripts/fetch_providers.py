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
        print(f"Providers already present in {dst} — nothing to do.")
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

    print(f"Done. Providers installed into {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
