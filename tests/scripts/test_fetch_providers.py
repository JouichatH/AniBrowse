"""Tests for the allanime ranking patch in scripts/fetch_providers.py.

The provider scrapers are fetched from the upstream viu-media wheel and are not
vendored in the repo, so the fork's best-first ranking edit ships as an
idempotent, version-pinned text patch applied right after fetch. These tests
pin that patch's behaviour against the exact upstream 3.5.0 body.
"""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "fetch_providers",
    Path(__file__).resolve().parents[2] / "scripts" / "fetch_providers.py",
)
assert _SPEC is not None and _SPEC.loader is not None
fp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fp)


# The exact upstream viu-media==3.5.0 body of AllAnime.episode_streams. The patch
# is anchored on the final `for source in sources:` loop; keep this in step with
# UPSTREAM_VERSION.
PRISTINE = '''\
    @debug_provider
    def episode_streams(self, params: EpisodeStreamsParams) -> Iterator[Server] | None:
        from .extractors import extract_server

        episode = self._get_episode_payload(params)
        if not episode:
            logger.error("nope")
            return

        sources = episode.get("sourceUrls") or []
        if not sources:
            logger.error("nope")
            return

        for source in sources:
            if server := extract_server(self.client, params.episode, episode, source):
                yield server
'''


def test_patch_pristine_applies():
    new_text, status = fp.apply_ranking_patch(PRISTINE)
    assert status == "patched"
    assert new_text != PRISTINE
    assert fp.RANKING_PATCH_MARKER in new_text
    # dedupe + priority sort landed in the body
    assert "_ranked.sort(" in new_text
    assert "for source in _ranked:" in new_text
    # the raw un-ranked loop is gone
    assert "for source in sources:\n            if server" not in new_text


def test_patch_is_idempotent():
    once, s1 = fp.apply_ranking_patch(PRISTINE)
    assert s1 == "patched"
    twice, s2 = fp.apply_ranking_patch(once)
    assert s2 == "already"
    assert twice == once  # second pass changes nothing


def test_patch_skips_unknown_shape():
    # An upstream version whose body no longer matches the pinned anchor must be
    # left untouched rather than corrupted.
    foreign = PRISTINE.replace("for source in sources:", "for src in sources:")
    new_text, status = fp.apply_ranking_patch(foreign)
    assert status == "skipped"
    assert new_text == foreign


# ---------------------------------------------------------------------------
# aaReq handshake patch
# ---------------------------------------------------------------------------

# Slim stand-ins for the upstream 3.5.0 files, containing every anchor the
# handshake patch keys on. Keep in step with UPSTREAM_VERSION.
PRISTINE_CONSTANTS = '''\
PERSISTED_QUERY_SHA256 = (
    "d405d0edd690624b66baba3068e0edc3ac90f1597d898a1ec8db4e5c43c00fec"
)
TOBEPARSED_DECRYPTION_SEED = "Xot36i3lK3:v1"

# search constants
DEFAULT_COUNTRY_OF_ORIGIN = "all"
'''

PRISTINE_UTILS = '''\
import functools
import hashlib
import json
import logging
import os
import re
from base64 import b64decode
from itertools import cycle
from typing import Any

from Cryptodome.Cipher import AES

logger = logging.getLogger(__name__)

# Dictionary to map hex values to characters
hex_to_char = {
    "01": "9",
}


def decode_tobeparsed(payload: str, key_seed: str) -> dict[str, Any]:
    base64_padding = (-len(payload)) % 4
    encrypted_payload = b64decode(payload + ("=" * base64_padding))
    iv = encrypted_payload[1:13]
    ciphertext = encrypted_payload[13:-16]
    decryption_key = hashlib.sha256(key_seed.encode("utf-8")).digest()

    plain_text = AES.new(
        decryption_key,
        AES.MODE_CTR,
        nonce=iv,
        initial_value=2,
    ).decrypt(ciphertext)

    return json.loads(plain_text.decode("utf-8"))
'''



def _pristine_from_anchors(name: str) -> str:
    """A minimal patchable input for a file: its own anchors concatenated.

    The patch is anchor->replacement; text containing each anchor verbatim is
    therefore patchable, regardless of how the (regenerated) anchors evolve.
    """
    return "\n\n".join(anchor for anchor, _ in fp._HANDSHAKE_EDITS[name])


def test_handshake_patch_applies_to_all_files():
    for name in ("constants.py", "utils.py", "provider.py"):
        new_text, status = fp.apply_handshake_patch(name, _pristine_from_anchors(name))
        assert status == "patched", name
        assert fp.HANDSHAKE_SENTINELS[name] in new_text, name


def test_handshake_patch_is_idempotent():
    once, s1 = fp.apply_handshake_patch("utils.py", PRISTINE_UTILS)
    assert s1 == "patched"
    twice, s2 = fp.apply_handshake_patch("utils.py", once)
    assert s2 == "already"
    assert twice == once


def test_handshake_patch_skips_unknown_shape():
    # A future upstream whose text no longer matches ANY anchor must be left
    # untouched — never half-patched.
    foreign = PRISTINE_UTILS.replace("def decode_tobeparsed", "def decode_blob")
    new_text, status = fp.apply_handshake_patch("utils.py", foreign)
    assert status == "skipped"
    assert new_text == foreign
    # unknown filename is also a skip
    _, status = fp.apply_handshake_patch("mappers.py", "whatever")
    assert status == "skipped"


def test_handshake_patch_recognizes_hand_fixed_copy():
    # The fork's development copy already carries the fix (without any marker
    # comment); the sentinel must classify it as "already", not corrupt it.
    fixed = "ALLANIME_KEY = \"abc\"\n"
    same, status = fp.apply_handshake_patch("constants.py", fixed)
    assert status == "already"
    assert same == fixed


def _exec_patched_utils() -> tuple[dict, dict]:
    """Execute the patched utils.py against the patched constants.py.

    Returns (utils_namespace, constants_namespace). The relative constants
    import is rewritten to a fake module fed from the executed constants.
    """
    import sys
    import types

    patched, status = fp.apply_handshake_patch("utils.py", PRISTINE_UTILS)
    assert status == "patched"
    consts, status = fp.apply_handshake_patch("constants.py", PRISTINE_CONSTANTS)
    assert status == "patched"
    const_ns: dict = {}
    exec(compile(consts, "<constants>", "exec"), const_ns)

    fake_constants = types.ModuleType("_fake_allanime_constants")
    for k in ("FALLBACK_KEYGEN", "KEYGEN_URLS"):
        setattr(fake_constants, k, const_ns[k])
    src = patched.replace(
        "from .constants import FALLBACK_KEYGEN, KEYGEN_URLS",
        "from _fake_allanime_constants import FALLBACK_KEYGEN, KEYGEN_URLS",
    )
    sys.modules["_fake_allanime_constants"] = fake_constants
    try:
        ns: dict = {}
        exec(compile(src, "<patched-utils>", "exec"), ns)
    finally:
        sys.modules.pop("_fake_allanime_constants", None)
    return ns, const_ns


def test_patched_get_aa_req_produces_valid_token():
    """The aaReq token must decrypt back to the signed payload (2026-07-20
    format: no buildId, iv from epoch:qh:ts) with the keygen's key."""
    import json as _json
    from base64 import b64decode as _b64decode

    from Cryptodome.Cipher import AES as _AES

    ns, const_ns = _exec_patched_utils()
    keygen = const_ns["FALLBACK_KEYGEN"]

    token = ns["get_aa_req"](keygen)
    raw = _b64decode(token)
    assert raw[0:1] == b"\x01"
    iv, ciphertext, tag = raw[1:13], raw[13:-16], raw[-16:]
    cipher = _AES.new(bytes.fromhex(keygen["key"]), _AES.MODE_GCM, nonce=iv)
    payload = _json.loads(cipher.decrypt_and_verify(ciphertext, tag))
    assert payload["epoch"] == keygen["epoch"]
    assert payload["qh"] == keygen["query_hash"]
    assert "buildId" not in payload
    assert payload["ts"] % (300 * 1000) == 0
    # iv is derived, not random: sha256("epoch:qh:ts")[:12]
    import hashlib as _hashlib

    expected_iv = _hashlib.sha256(
        f"{keygen['epoch']}:{keygen['query_hash']}:{payload['ts']}".encode()
    ).digest()[:12]
    assert iv == expected_iv


def test_patched_decode_tobeparsed_tries_both_keys():
    """decode_tobeparsed authenticates with the rotating key OR the legacy
    sha256(static seed) key, and rejects blobs matching neither."""
    import hashlib as _hashlib
    import json as _json
    from base64 import b64encode as _b64encode

    import pytest
    from Cryptodome.Cipher import AES as _AES

    ns, const_ns = _exec_patched_utils()
    keygen = const_ns["FALLBACK_KEYGEN"]
    blob = _json.dumps({"episode": {"n": 1}}).encode()
    iv12 = b"\x00" * 12

    def envelope(key: bytes) -> str:
        ct, tag = _AES.new(key, _AES.MODE_GCM, nonce=iv12).encrypt_and_digest(blob)
        return _b64encode(b"\x01" + iv12 + ct + tag).decode()

    rotating = bytes.fromhex(keygen["key"])
    legacy = _hashlib.sha256(keygen["static_key"].encode()).digest()
    for key in (rotating, legacy):
        assert ns["decode_tobeparsed"](envelope(key), keygen) == {"episode": {"n": 1}}

    with pytest.raises(ValueError):
        ns["decode_tobeparsed"](envelope(b"\x42" * 32), keygen)


def test_patched_body_ranks_best_first():
    """Execute the patched episode_streams to prove best-first + dedupe order."""
    patched, _ = fp.apply_ranking_patch(PRISTINE)

    # Build a runnable stand-in class exposing only what the method touches.
    ns: dict = {}
    src = (
        "from typing import Iterator\n"
        "class Server: pass\n"
        "class EpisodeStreamsParams: pass\n"
        "def debug_provider(f): return f\n"
        "class logger:\n"
        "    @staticmethod\n"
        "    def error(*a, **k): pass\n"
        "extract_server = None\n"  # patched-in below via a fake module
        "class AllAnime:\n" + patched
    )
    # `from .extractors import extract_server` inside the method needs a real
    # module; inject a fake that echoes the source's sourceName.
    import sys
    import types

    fake_extractors = types.ModuleType("_fake_extractors")
    setattr(
        fake_extractors,
        "extract_server",
        lambda client, ep, episode, source: source.get("sourceName"),
    )
    # Rewrite the relative import to the fake module name.
    src = src.replace(
        "from .extractors import extract_server",
        "from _fake_extractors import extract_server",
    )
    sys.modules["_fake_extractors"] = fake_extractors
    try:
        exec(compile(src, "<patched>", "exec"), ns)
        AllAnime = ns["AllAnime"]
        inst = AllAnime()
        inst.client = None
        inst._get_episode_payload = lambda params: {
            "sourceUrls": [
                {"sourceName": "Mp4-upload", "priority": 4.0},
                {"sourceName": "Mp4-upload", "priority": 4.0},  # dup -> dropped
                {"sourceName": "Yt-mp4", "priority": 7.9},
                {"sourceName": "Default", "priority": 5.5},
                {"sourceName": "NoPrio"},  # missing priority -> 0.0, last
            ]
        }

        class P:
            episode = "9"
            translation_type = "sub"

        assert list(inst.episode_streams(P())) == [
            "Yt-mp4",
            "Default",
            "Mp4-upload",
            "NoPrio",
        ]
    finally:
        sys.modules.pop("_fake_extractors", None)
