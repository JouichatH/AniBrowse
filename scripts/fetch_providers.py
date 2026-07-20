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

import json
import shutil
import sys
import tempfile
import urllib.request
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
# Instead we reproduce each fork edit here (this ranking patch and the aaReq
# handshake patch above) as idempotent, version-pinned text patches applied
# right after fetch. Each provider is expected
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


# ---------------------------------------------------------------------------
# allanime aaReq handshake patch (ported from pystardust/ani-cli's `fix` branch,
# live-verified 2026-07-17; see the fork's provider-fix notes).
#
# Upstream viu-media 3.5.0 (the wheel we fetch) predates allanime's server-side
# anti-scrape gate: without a signed `aaReq` token in the source request the API
# answers AA_CRYPTO_MISSING and every episode resolves to zero servers, so the
# app silently lives on the nyaa fallback. Like the ranking patch, the fix is a
# set of anchored, all-or-nothing text edits applied right after fetch: if any
# anchor is missing (unknown upstream shape) the file is left untouched.
#
# Idempotency is keyed on the patched code itself (sentinels below) rather than
# a marker comment so the patched result stays byte-identical to the fork's
# hand-fixed development copy.
#
# TREADMILL NOTE: allanime rotates its crypto values every few days, so the
# patched code fetches them AT RUNTIME (utils.fetch_keygen -> KEYGEN_URLS,
# incl. this repo's keygen/allanime.json) instead of trusting baked-in values.
# When streams break with AA_CRYPTO_STALE / AA_CRYPTO_MISSING:
#   1. python scripts/allanime_keygen.py     (re-extracts values from the live
#      site and rewrites keygen/allanime.json - push it and installs heal)
#   2. If the FORMAT changed (values alone don't fix it), edit the local
#      allanime files, then regenerate this patch with
#      python dev/regen_handshake_patch.py (verifies wheel+patch == local).
HANDSHAKE_SENTINELS = {
    "constants.py": "ALLANIME_KEY =",
    "utils.py": "def get_aa_req",
    "provider.py": "get_aa_req",
}

# --- BEGIN GENERATED HANDSHAKE EDITS (dev/regen_handshake_patch.py) ---
_HANDSHAKE_EDITS: dict[str, list[tuple[str, str]]] = {
    'constants.py': [
        ('TOBEPARSED_DECRYPTION_SEED = "Xot36i3lK3:v1"\n\n# search constants',
         '# Legacy seed: sha256(seed) is still one accepted key for the tobeparsed\n# response blob (tried second, after the rotating key).\nTOBEPARSED_DECRYPTION_SEED = "Xot36i3lK3:v1"\n\n# aaReq crypto values required by the allanime source endpoint. They rot every\n# few days (the "crypto treadmill"), so at runtime utils.fetch_keygen() pulls\n# the CURRENT values from KEYGEN_URLS (first parseable source wins) and only\n# falls back to the baked-in values below when every source is unreachable.\n# 2026-07-20 rotation: the token payload dropped buildId, the iv is now\n# sha256(f"{epoch}:{qh}:{ts}"), and the persisted-query hash rotates with the\n# client (qh below superseded the old d405d0ed... hash).\nKEYGEN_URLS = [\n    # anipy-cli\'s CI re-scrapes the site and refreshes this on every rotation.\n    "https://raw.githubusercontent.com/sdaqo/anipy-cli/refs/heads/key-gen/scripts/keygen/keygen.json",\n    # Fork-owned copy: updating this one file on GitHub heals every install\n    # at next launch, without touching installed code.\n    "https://raw.githubusercontent.com/JouichatH/AniBrowse/master/keygen/allanime.json",\n]\nALLANIME_KEY = "cf4777b5778aeadc9449e12769ea545d00c43cd8ff65d482364586cde204f359"\nALLANIME_EPOCH = 4130\nALLANIME_QUERY_HASH = (\n    "09caca435564416f37d5c78256c8e6e517007c3006529857e84ba2466bfcbea6"\n)\nFALLBACK_KEYGEN = {\n    "epoch": ALLANIME_EPOCH,\n    "key": ALLANIME_KEY,\n    "query_hash": ALLANIME_QUERY_HASH,\n    "static_key": TOBEPARSED_DECRYPTION_SEED,\n}\n\n# search constants'),
    ],
    'utils.py': [
        ('import logging\nimport os\nimport re\nfrom base64 import b64decode\nfrom itertools import cycle',
         'import logging\nimport os\nimport re\nimport time\nfrom base64 import b64decode, b64encode\nfrom itertools import cycle'),
        ('from Cryptodome.Cipher import AES\n\nlogger = logging.getLogger(__name__)\n\n# Dictionary to map hex values to characters',
         'from Cryptodome.Cipher import AES\n\nfrom .constants import FALLBACK_KEYGEN, KEYGEN_URLS\n\nlogger = logging.getLogger(__name__)\n\n_KEYGEN_FIELDS = ("epoch", "key", "query_hash")\n_KEYGEN_CACHE_TTL = 3 * 60 * 60  # seconds; rotations happen every few days\n_KEYGEN_FORCE_COOLDOWN = 10 * 60  # don\'t hammer sources when values stay stale\n_keygen_memory: dict[str, Any] | None = None\n_keygen_last_force: float = 0.0\n\n\ndef _keygen_cache_file() -> "Any":\n    from .....core.constants import APP_CACHE_DIR\n\n    return APP_CACHE_DIR / "allanime_keygen.json"\n\n\ndef fetch_keygen(force: bool = False) -> dict[str, Any]:\n    """Current allanime crypto values (epoch / key / query_hash / static_key).\n\n    The values rot every few days, so hardcoding them breaks the provider at\n    every rotation. Instead: in-memory -> disk cache (TTL) -> KEYGEN_URLS in\n    order (first parseable wins) -> baked-in FALLBACK_KEYGEN. ``force=True``\n    skips every cache and refetches (used for the retry after the server\n    rejects a token as stale).\n    """\n    global _keygen_memory, _keygen_last_force\n    if force:\n        # A forced refresh means the server rejected our token. If the sources\n        # haven\'t been re-checked recently they might have fresh values; if we\n        # refreshed moments ago, refetching again would just repeat the same\n        # stale answer for every episode attempt - back off.\n        if time.time() - _keygen_last_force < _KEYGEN_FORCE_COOLDOWN:\n            return _keygen_memory or dict(FALLBACK_KEYGEN)\n        _keygen_last_force = time.time()\n    if _keygen_memory is not None and not force:\n        return _keygen_memory\n\n    cache_file = _keygen_cache_file()\n    if not force:\n        try:\n            cached = json.loads(cache_file.read_text(encoding="utf-8"))\n            if time.time() - cached["fetched_at"] < _KEYGEN_CACHE_TTL:\n                keygen = cached["keygen"]\n                if all(f in keygen for f in _KEYGEN_FIELDS):\n                    _keygen_memory = keygen\n                    return keygen\n        except Exception:  # noqa: BLE001 - any cache problem just means refetch\n            pass\n\n    import urllib.request\n\n    for url in KEYGEN_URLS:\n        try:\n            with urllib.request.urlopen(url, timeout=5) as r:\n                keygen = json.loads(r.read().decode("utf-8"))\n            if not all(f in keygen for f in _KEYGEN_FIELDS):\n                logger.warning("keygen source %s missing fields; skipping", url)\n                continue\n            keygen.setdefault("static_key", FALLBACK_KEYGEN["static_key"])\n            _keygen_memory = keygen\n            try:\n                cache_file.write_text(\n                    json.dumps({"fetched_at": time.time(), "keygen": keygen}),\n                    encoding="utf-8",\n                )\n            except OSError:\n                pass\n            logger.debug("allanime keygen refreshed from %s", url)\n            return keygen\n        except Exception as e:  # noqa: BLE001 - try the next source\n            logger.warning("keygen source %s failed: %s", url, e)\n\n    logger.warning("all keygen sources failed; using baked-in fallback values")\n    _keygen_memory = dict(FALLBACK_KEYGEN)\n    return _keygen_memory\n\n\ndef get_aa_req(keygen: dict[str, Any] | None = None) -> str:\n    """Build the signed ``aaReq`` token the allanime source endpoint requires.\n\n    2026-07-20 format (mirrors sdaqo/anipy-cli): payload has no buildId and\n    the iv derives from ``epoch:qh:ts``. A 5-minute-bucketed timestamp is\n    signed via AES-256-GCM and packaged as base64(0x01 || iv || ct || tag).\n    Without a valid token the API returns AA_CRYPTO_MISSING / AA_CRYPTO_STALE\n    and no sources.\n    """\n    if keygen is None:\n        keygen = fetch_keygen()\n    ts = int(time.time() * 1000) // 300000 * 300000\n    qh = keygen["query_hash"]\n    payload = json.dumps(\n        {"v": 1, "ts": ts, "epoch": keygen["epoch"], "qh": qh},\n        separators=(",", ":"),\n    ).encode()\n    iv = hashlib.sha256(f"{keygen[\'epoch\']}:{qh}:{ts}".encode()).digest()[:12]\n    cipher = AES.new(bytes.fromhex(keygen["key"]), AES.MODE_GCM, nonce=iv)\n    ciphertext, tag = cipher.encrypt_and_digest(payload)\n    return b64encode(b"\\x01" + iv + ciphertext + tag).decode()\n\n# Dictionary to map hex values to characters'),
        ('def decode_tobeparsed(payload: str, key_seed: str) -> dict[str, Any]:\n    base64_padding = (-len(payload)) % 4\n    encrypted_payload = b64decode(payload + ("=" * base64_padding))\n    iv = encrypted_payload[1:13]\n    ciphertext = encrypted_payload[13:-16]\n    decryption_key = hashlib.sha256(key_seed.encode("utf-8")).digest()\n\n    plain_text = AES.new(\n        decryption_key,\n        AES.MODE_CTR,\n        nonce=iv,\n        initial_value=2,\n    ).decrypt(ciphertext)\n\n    return json.loads(plain_text.decode("utf-8"))',
         'def decode_tobeparsed(payload: str, keygen: dict[str, Any] | None = None) -> dict[str, Any]:\n    # The source blob is AES-256-GCM: 0x01 || iv(12) || ciphertext || tag(16).\n    # It is keyed with either the rotating aaReq key or the legacy\n    # sha256(static seed) key; try both and use whichever authenticates.\n    if keygen is None:\n        keygen = fetch_keygen()\n    base64_padding = (-len(payload)) % 4\n    encrypted_payload = b64decode(payload + ("=" * base64_padding))\n    iv = encrypted_payload[1:13]\n    ciphertext = encrypted_payload[13:-16]\n    tag = encrypted_payload[-16:]\n\n    candidates = [\n        bytes.fromhex(keygen["key"]),\n        hashlib.sha256(str(keygen.get("static_key", "")).encode("utf-8")).digest(),\n    ]\n    last_error: Exception | None = None\n    for key in candidates:\n        try:\n            plain_text = AES.new(key, AES.MODE_GCM, nonce=iv).decrypt_and_verify(\n                ciphertext, tag\n            )\n            return json.loads(plain_text.decode("utf-8"))\n        except (ValueError, KeyError) as e:\n            last_error = e\n    raise ValueError(f"tobeparsed did not authenticate with any known key: {last_error}")'),
    ],
    'provider.py': [
        ('from .constants import (\n    ANIME_GQL,\n    API_EPISODE_HEADERS,\n    API_GRAPHQL_ENDPOINT,\n    API_GRAPHQL_HEADERS,\n    API_GRAPHQL_REFERER,\n    EPISODE_GQL,\n    PERSISTED_QUERY_SHA256,\n    SEARCH_GQL,\n    TOBEPARSED_DECRYPTION_SEED,\n)\n',
         'from .constants import (\n    ANIME_GQL,\n    API_EPISODE_HEADERS,\n    API_GRAPHQL_ENDPOINT,\n    API_GRAPHQL_HEADERS,\n    API_GRAPHQL_REFERER,\n    EPISODE_GQL,\n    SEARCH_GQL,\n)\n'),
        ('from .utils import decode_tobeparsed\n',
         'from .utils import decode_tobeparsed, fetch_keygen, get_aa_req\n'),
        ('decode_tobeparsed(encoded_payload, TOBEPARSED_DECRYPTION_SEED)',
         'decode_tobeparsed(encoded_payload)'),
        ('    def _get_episode_payload(self, params: EpisodeStreamsParams) -> AllAnimeEpisode | None:\n        persisted_query_response = self.client.get(\n            API_GRAPHQL_ENDPOINT,\n            params={\n                "variables": dumps(\n                    {\n                        "showId": params.anime_id,\n                        "translationType": params.translation_type,\n                        "episodeString": params.episode,\n                    },\n                    separators=(",", ":"),\n                ),\n                "extensions": dumps(\n                    {\n                        "persistedQuery": {\n                            "version": 1,\n                            "sha256Hash": PERSISTED_QUERY_SHA256,\n                        }\n                    },\n                    separators=(",", ":"),\n                ),\n            },\n            headers={**API_GRAPHQL_HEADERS, **API_EPISODE_HEADERS},\n        )\n        persisted_query_response.raise_for_status()\n\n        if episode := self._extract_episode_from_payload(persisted_query_response.json()):\n            return episode\n\n        episode_response = execute_graphql(\n            API_GRAPHQL_ENDPOINT,\n            self.client,\n            EPISODE_GQL,\n            variables={\n                "showId": params.anime_id,\n                "translationType": params.translation_type,\n                "episodeString": params.episode,\n            },\n            headers=API_GRAPHQL_HEADERS,\n        )\n        return self._extract_episode_from_payload(episode_response.json())',
         '    def _persisted_episode_query(\n        self, params: EpisodeStreamsParams, force_keygen: bool\n    ) -> dict[str, Any]:\n        """One signed persisted-query GET; returns the raw response payload."""\n        keygen = fetch_keygen(force=force_keygen)\n        persisted_query_response = self.client.get(\n            API_GRAPHQL_ENDPOINT,\n            params={\n                "variables": dumps(\n                    {\n                        "showId": params.anime_id,\n                        "translationType": params.translation_type,\n                        "episodeString": params.episode,\n                    },\n                    separators=(",", ":"),\n                ),\n                "extensions": dumps(\n                    {\n                        "persistedQuery": {\n                            "version": 1,\n                            "sha256Hash": keygen["query_hash"],\n                        },\n                        "aaReq": get_aa_req(keygen),\n                    },\n                    separators=(",", ":"),\n                ),\n            },\n            headers={**API_GRAPHQL_HEADERS, **API_EPISODE_HEADERS},\n        )\n        persisted_query_response.raise_for_status()\n        return persisted_query_response.json()\n\n    @staticmethod\n    def _is_crypto_rejection(payload: dict[str, Any]) -> bool:\n        return any(\n            "AA_CRYPTO" in str(err.get("message", ""))\n            for err in payload.get("errors") or []\n        )\n\n    def _get_episode_payload(self, params: EpisodeStreamsParams) -> AllAnimeEpisode | None:\n        payload = self._persisted_episode_query(params, force_keygen=False)\n        if self._is_crypto_rejection(payload):\n            # Cached/baked crypto values went stale (the treadmill rotated).\n            # Refetch the keygen from the network sources and retry once.\n            logger.info("allanime rejected the aaReq token; refreshing keygen and retrying")\n            payload = self._persisted_episode_query(params, force_keygen=True)\n\n        if episode := self._extract_episode_from_payload(payload):\n            return episode\n\n        episode_response = execute_graphql(\n            API_GRAPHQL_ENDPOINT,\n            self.client,\n            EPISODE_GQL,\n            variables={\n                "showId": params.anime_id,\n                "translationType": params.translation_type,\n                "episodeString": params.episode,\n            },\n            headers=API_GRAPHQL_HEADERS,\n        )\n        return self._extract_episode_from_payload(episode_response.json())'),
    ],
}
# --- END GENERATED HANDSHAKE EDITS ---


def apply_handshake_patch(filename: str, text: str) -> tuple[str, str]:
    """Apply the aaReq handshake patch to one allanime source file's text.

    Pure and idempotent, mirroring ``apply_ranking_patch``. Returns
    ``(new_text, status)`` where status is ``"already"``, ``"skipped"``
    (unknown file or any anchor missing — nothing is half-applied), or
    ``"patched"``.
    """
    edits = _HANDSHAKE_EDITS.get(filename)
    sentinel = HANDSHAKE_SENTINELS.get(filename)
    if edits is None or sentinel is None:
        return text, "skipped"
    if sentinel in text:
        return text, "already"
    if any(anchor not in text for anchor, _ in edits):
        return text, "skipped"
    for anchor, replacement in edits:
        text = text.replace(anchor, replacement, 1)
    return text, "patched"


def _patch_allanime_handshake(dst: Path) -> None:
    """Idempotently patch the fetched allanime provider for the aaReq handshake."""
    allanime = dst / "allanime"
    if not (allanime / "provider.py").exists():
        return
    for filename in _HANDSHAKE_EDITS:
        target = allanime / filename
        if not target.exists():
            print(
                f"  warning: allanime/{filename} missing; handshake patch NOT applied.",
                file=sys.stderr,
            )
            continue
        original = target.read_text(encoding="utf-8")
        new_text, status = apply_handshake_patch(filename, original)
        if status == "patched":
            target.write_text(new_text, encoding="utf-8")
            print(f"  patched allanime/{filename}: aaReq handshake applied")
        elif status == "already":
            print(f"  allanime/{filename}: handshake patch already present")
        else:  # skipped
            print(
                f"  warning: allanime/{filename} did not match the pinned "
                f"viu-media=={UPSTREAM_VERSION} shape; handshake patch NOT "
                "applied — allanime sources will fail with AA_CRYPTO_MISSING.",
                file=sys.stderr,
            )


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


def _download_wheel(tmpdir: Path) -> Path | None:
    """Download the upstream wheel from PyPI with the stdlib only.

    Deliberately NOT `pip download`: venvs created by uv (the Windows
    installer) ship without pip, so shelling out to pip broke there. The
    wheel's direct URL from PyPI's JSON API is all we need.
    """
    meta_url = f"https://pypi.org/pypi/viu-media/{UPSTREAM_VERSION}/json"
    with urllib.request.urlopen(meta_url, timeout=30) as r:
        meta = json.load(r)
    wheel = next(
        (u for u in meta.get("urls", []) if u.get("packagetype") == "bdist_wheel"),
        None,
    )
    if not wheel:
        return None
    out = tmpdir / wheel["filename"]
    with urllib.request.urlopen(wheel["url"], timeout=120) as r, open(out, "wb") as fh:
        shutil.copyfileobj(r, fh)
    return out


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
        # Still (idempotently) ensure the fork patches are applied to a
        # pre-existing install (this also repairs installs fetched before a
        # patch existed — e.g. the aaReq handshake fix).
        _patch_allanime_handshake(dst)
        _patch_allanime_ranking(dst)
        return 0

    print(f"Fetching providers {missing} from viu-media=={UPSTREAM_VERSION} ...")
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        try:
            wheel_path = _download_wheel(tmpdir)
        except Exception as e:  # noqa: BLE001 - any network/parse failure -> actionable msg
            print(f"error: failed to download the viu-media wheel ({e}).", file=sys.stderr)
            return 1
        if not wheel_path:
            print(
                f"error: no wheel on PyPI for viu-media=={UPSTREAM_VERSION}.",
                file=sys.stderr,
            )
            return 1

        with zipfile.ZipFile(wheel_path) as zf:
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

    _patch_allanime_handshake(dst)
    _patch_allanime_ranking(dst)
    print(f"Done. Providers installed into {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
