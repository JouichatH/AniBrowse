"""Tests for the third-party embed extractors (pure logic - no network).

These pin the parsing/decryption of allanime's current embed sources (ok.ru,
uns.bio) and the dispatch that routes them - and that captcha-gated Fm-Hls stays
unsupported. Real hosts are exercised live during development; here we feed the
extractors canned responses so CI stays offline and deterministic.
"""

import html
import json

from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad

from viu_media.libs.provider.anime import embed_extractors as EE


class _Resp:
    def __init__(self, text: str, status: int = 200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _Client:
    """Minimal httpx.Client stand-in: maps URL substrings to canned responses."""

    def __init__(self, routes: dict[str, _Resp]):
        self._routes = routes
        self.calls: list[str] = []

    def get(self, url, **kw):
        self.calls.append(url)
        for needle, resp in self._routes.items():
            if needle in url:
                return resp
        raise AssertionError(f"unexpected GET {url}")


EPISODE = {"notes": "Test Episode"}


# --------------------------------------------------------------------------- #
# Ok (ok.ru)
# --------------------------------------------------------------------------- #
def _ok_page(metadata: dict) -> str:
    blob = html.escape(json.dumps({"flashvars": {"metadata": json.dumps(metadata)}}))
    return f'<div id="movie" data-options="{blob}"></div>'


def test_extract_ok_returns_hls_and_mp4_links():
    metadata = {
        "hlsManifestUrl": "https://cdn.example/video.m3u8?sig=abc",
        "videos": [
            {"name": "hd", "url": "https://cdn.example/hd.mp4"},
            {"name": "mobile", "url": "https://cdn.example/mobile.mp4"},
        ],
    }
    client = _Client({"ok.ru": _Resp(_ok_page(metadata))})
    server = EE.extract_ok("https://ok.ru/videoembed/123", client, EPISODE, {})

    assert server is not None
    assert server.name == "ok"
    assert server.headers["Referer"] == "https://ok.ru/"
    hls = [l for l in server.links if l.hls]
    assert len(hls) == 1 and hls[0].link.endswith(".m3u8?sig=abc")
    mp4 = [l for l in server.links if l.mp4]
    assert {l.quality for l in mp4} == {"1080", "360"}


def test_extract_ok_without_data_options_returns_none():
    client = _Client({"ok.ru": _Resp("<html>no options here</html>")})
    assert EE.extract_ok("https://ok.ru/videoembed/123", client, EPISODE, {}) is None


# --------------------------------------------------------------------------- #
# Uni (allanime.uns.bio) - AES-128-CBC with a per-host-static key/iv.
# --------------------------------------------------------------------------- #
def _uni_encrypt(payload: dict) -> str:
    raw = pad(json.dumps(payload).encode(), 16)
    return AES.new(EE._UNI_KEY, AES.MODE_CBC, EE._UNI_IV).encrypt(raw).hex()


def test_extract_uni_decrypts_and_returns_hls():
    payload = {
        "source": "https://origin.example/master.m3u8",
        "cfNative": "https://allanime.uns.bio/v4/pl/x/master.m3u8?k=zzz",
    }
    client = _Client({"/api/v1/video": _Resp(_uni_encrypt(payload))})
    server = EE.extract_uni("https://allanime.uns.bio/#vxw8fb", client, EPISODE, {})

    assert server is not None
    assert server.name == "uni"
    # id parsed from the fragment
    assert "id=vxw8fb" in client.calls[0]
    links = [l.link for l in server.links]
    # cfNative first, both present, all flagged hls
    assert links[0] == payload["cfNative"]
    assert payload["source"] in links
    assert all(l.hls for l in server.links)


def test_extract_uni_strips_extra_fragment_params():
    payload = {"source": "https://origin.example/master.m3u8"}
    client = _Client({"/api/v1/video": _Resp(_uni_encrypt(payload))})
    EE.extract_uni("https://allanime.uns.bio/#abc123&foo=bar", client, EPISODE, {})
    assert "id=abc123&" in client.calls[0] + "&"  # id is just 'abc123'
    assert "id=abc123&w=" in client.calls[0]


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #
def test_extract_embed_unsupported_source_returns_none():
    client = _Client({})
    # Fm-Hls is captcha-gated and deliberately unsupported.
    assert EE.extract_embed("Fm-Hls", "https://bysekoze.com/e/x", client, EPISODE, {}) is None
    assert EE.extract_embed("Whatever", "https://x/y", client, EPISODE, {}) is None


def test_registry_covers_ok_and_uni_only():
    assert set(EE.EMBED_EXTRACTORS) == {"Ok", "Uni"}
