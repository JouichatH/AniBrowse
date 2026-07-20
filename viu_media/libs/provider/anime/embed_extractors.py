"""Server-side extractors for allanime's current third-party embed sources.

As of the 2026-07 allanime/mkissa split, the episode ``sourceUrls`` are no
longer internal ``/apivtwo/clock`` links - they are direct third-party iframe
embeds (bysekoze/Filemoon, uns.bio, ok.ru, mp4upload). The upstream viu-media
extractors assume the old clock format, so they no longer resolve these.

This module lives in the TRACKED provider package (not the gitignored allanime/
scraper), mirroring token_capture.py: the gitignored dispatch is patched to call
``extract_embed`` so the real logic survives a fresh install / provider refetch.

Coverage (probed live against Mushoku Tensei S3, 2026-07-20):
  * Ok  (ok.ru)          - metadata JSON in the embed page -> HLS master + mp4s.
  * Uni (allanime.uns.bio) - AES-128-CBC encrypted JSON API -> HLS master.
  * Fm-Hls (bysekoze)    - NOT extractable: gated behind an interactive
    "click to verify you are human" captcha plus popup ads. The whole community
    (ani-cli, AniPlay) leaves Filemoon unsupported for the same reason.
"""

from __future__ import annotations

import html
import json
import re
from typing import Any, Callable

from httpx import Client

from .types import EpisodeStream, Server, Subtitle

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _title(episode: dict[str, Any]) -> str | None:
    return episode.get("notes") if isinstance(episode, dict) else None


# --------------------------------------------------------------------------- #
# Ok - ok.ru public embed. The player config sits in a data-options attribute
# on the embed page; flashvars.metadata carries an HLS master plus per-quality
# mp4 URLs. No auth, no bot wall.
# --------------------------------------------------------------------------- #
_OK_QUALITY = {
    "full": "1080",
    "hd": "1080",
    "sd": "720",
    "low": "480",
    "lowest": "360",
    "mobile": "360",
}


def extract_ok(
    url: str, client: Client, episode: dict[str, Any], source: dict[str, Any]
) -> Server | None:
    resp = client.get(
        url, headers={"User-Agent": _UA, "Referer": "https://mkissa.to/"},
        timeout=15, follow_redirects=True,
    )
    resp.raise_for_status()
    m = re.search(r'data-options="([^"]+)"', resp.text)
    if not m:
        return None
    opts = json.loads(html.unescape(m.group(1)))
    metadata = opts.get("flashvars", {}).get("metadata")
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    if not isinstance(metadata, dict):
        return None

    links: list[EpisodeStream] = []
    hls = metadata.get("hlsManifestUrl") or metadata.get("hlsMasterPlaylistUrl")
    if hls:
        links.append(EpisodeStream(link=hls, quality="1080", hls=True))
    for video in metadata.get("videos", []) or []:
        link = video.get("url")
        if link:
            links.append(
                EpisodeStream(
                    link=link,
                    quality=_OK_QUALITY.get(video.get("name", ""), "720"),
                    mp4=True,
                )
            )
    if not links:
        return None
    return Server(
        name="ok",
        links=links,
        episode_title=_title(episode),
        headers={"Referer": "https://ok.ru/", "User-Agent": _UA},
    )


# --------------------------------------------------------------------------- #
# Uni - allanime.uns.bio. The video id is the URL fragment; the /api/v1/video
# response is an AES-128-CBC blob (hex) with a per-host-static key/iv derived
# from window.location.host. The decrypted JSON exposes the HLS master directly
# (``source`` = origin CDN, ``cfNative`` = same-domain proxy fallback).
# Key/iv captured live from the site's WebCrypto calls (host allanime.uns.bio).
# --------------------------------------------------------------------------- #
_UNI_KEY = b"kiemtienmua911ca"
_UNI_IV = b"1234567890oiuytr"


def _uni_decrypt(hex_blob: str) -> Any:
    from Cryptodome.Cipher import AES
    from Cryptodome.Util.Padding import unpad

    raw = bytes.fromhex(hex_blob.strip())
    plain = unpad(AES.new(_UNI_KEY, AES.MODE_CBC, _UNI_IV).decrypt(raw), 16)
    return json.loads(plain.decode("utf-8", "replace"))


def extract_uni(
    url: str, client: Client, episode: dict[str, Any], source: dict[str, Any]
) -> Server | None:
    # allanime.uns.bio/#vxw8fb  ->  id = vxw8fb (fragment; strip any &-params)
    frag = url.split("#", 1)[1] if "#" in url else url.rstrip("/").rsplit("/", 1)[-1]
    video_id = frag.split("&", 1)[0]
    if not video_id:
        return None

    base = "https://allanime.uns.bio"
    headers = {"User-Agent": _UA, "Referer": base + "/"}
    resp = client.get(
        f"{base}/api/v1/video?id={video_id}&w=1920&h=1080&r=",
        headers=headers, timeout=15, follow_redirects=True,
    )
    resp.raise_for_status()
    data = _uni_decrypt(resp.text)
    if not isinstance(data, dict):
        return None

    links: list[EpisodeStream] = []
    # cfNative is proxied through the uns.bio domain (most reliable); source is
    # the raw origin CDN. Offer both, cfNative first.
    for key in ("cfNative", "source"):
        link = data.get(key)
        if link and link not in (s.link for s in links):
            links.append(EpisodeStream(link=link, quality="1080", hls=True))
    if not links:
        return None

    subtitles: list[Subtitle] = []
    for track in data.get("tracks", []) or []:
        if isinstance(track, dict) and track.get("file") and track.get("kind") == "captions":
            subtitles.append(Subtitle(url=track["file"], language=track.get("label")))

    return Server(
        name="uni",
        links=links,
        episode_title=_title(episode),
        headers={"Referer": base + "/", "User-Agent": _UA},
        subtitles=subtitles,
    )


# --------------------------------------------------------------------------- #
# Dispatch. Keys match allanime's ``sourceName`` values.
# --------------------------------------------------------------------------- #
EMBED_EXTRACTORS: dict[str, Callable[..., Server | None]] = {
    "Ok": extract_ok,
    "Uni": extract_uni,
}


def extract_embed(
    source_name: str,
    url: str,
    client: Client,
    episode: dict[str, Any],
    source: dict[str, Any],
) -> Server | None:
    """Resolve a third-party embed ``sourceName`` to a playable Server.

    Returns None for unsupported sources (e.g. Fm-Hls, which is captcha-gated).
    """
    fn = EMBED_EXTRACTORS.get(source_name)
    if fn is None:
        return None
    return fn(url, client, episode, source)
