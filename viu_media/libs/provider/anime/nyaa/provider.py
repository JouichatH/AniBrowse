"""Nyaa torrent provider for ani-browse.

Nyaa (nyaa.si) indexes fansub torrents. Unlike streaming providers it exposes
one torrent per weekly release, so this provider maps a show to the set of
episodes available as torrents and returns a magnet link per episode. Playback
is handled by the mpv player, which detects the magnet (TORRENT_REGEX) and
streams it via ``webtorrent --mpv``.

Why nyaa: it is reachable without the Cloudflare / DDoS-Guard walls that block
the streaming sources, it carries the fastest simulcast releases (SubsPlease /
Erai-raws post within roughly an hour of a broadcast), and the subs are English.
The trade-off is fuzzy title matching (fansub names differ from AniList titles)
and that watching seeds while you play (P2P).
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, ClassVar, Dict, List
from urllib.parse import quote
from xml.etree import ElementTree

from ..base import BaseAnimeProvider
from ..types import (
    Anime,
    AnimeEpisodeInfo,
    AnimeEpisodes,
    EpisodeStream,
    MediaTranslationType,
    PageInfo,
    SearchResult,
    SearchResults,
    Server,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from ..params import AnimeParams, EpisodeStreamsParams, SearchParams

logger = logging.getLogger(__name__)

NYAA_URL = "https://nyaa.si/"
NYAA_NS = "{https://nyaa.si/xmlns/nyaa}"
ANIME_ENG_CATEGORY = "1_2"  # Anime - English-translated

# Fansub groups in quality/reliability order; used to break ties between
# duplicate uploads of the same episode.
PREFERRED_GROUPS = ["SubsPlease", "Erai-raws", "EMBER", "Judas", "ASW", "Anime Time"]

TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "http://nyaa.tracker.wf:7777/announce",
]

_GROUP_RE = re.compile(r"^\[([^\]]+)\]")
# " - 03 ", " - 03v2 (", "S3 - 03 [" etc. -> episode number (leading zeros stripped)
_EP_RE = re.compile(r"\s-\s0*(\d+(?:\.\d+)?)(?:v\d+)?(?=\s|$|\(|\[)")
_RES_RE = re.compile(r"(\d{3,4})p")
_BATCH_RE = re.compile(r"[(\[]\s*0*\d+\s*[-~]\s*0*\d+\s*[)\]]")  # (01-12) season batch


class Nyaa(BaseAnimeProvider):
    HEADERS: ClassVar[Dict[str, str]] = {}

    # ---- query building ------------------------------------------------
    @staticmethod
    def _search_variants(title: str) -> List[str]:
        """Turn an AniList title into nyaa query variants, most specific first.

        Fansubs name seasons like "Mushoku Tensei S3", not
        "Mushoku Tensei III: Isekai Ittara Honki Dasu", so we generate a few
        forms and try them in order until one yields single-episode torrents.
        """
        base = title.split(": ")[0].strip()  # drop a ": Subtitle" suffix only
        roman = {"ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6}
        root, season = base, None

        m = re.search(r"\b(ii|iii|iv|v|vi)\s*$", base, re.IGNORECASE)
        m2 = re.search(
            r"\b(?:season\s*(\d+)|(\d+)(?:st|nd|rd|th)\s*season|part\s*(\d+))\b",
            title,
            re.IGNORECASE,
        )
        if m:
            season = roman[m.group(1).lower()]
            root = base[: m.start()].strip()
        elif m2:
            season = int(next(g for g in m2.groups() if g))
            root = re.split(r"\b(?:season|part)\b", base, flags=re.IGNORECASE)[0].strip()

        variants: List[str] = []
        if season:
            variants += [f"{root} S{season}", f"{root} Season {season}"]
        variants.append(base)
        if root != base:
            variants.append(root)

        seen, out = set(), []
        for v in variants:
            k = v.lower()
            if v and k not in seen:
                seen.add(k)
                out.append(v)
        return out

    # ---- nyaa fetch/parse ---------------------------------------------
    def _fetch(self, query: str) -> List[dict]:
        url = f"{NYAA_URL}?page=rss&q={quote(query)}&c={ANIME_ENG_CATEGORY}&f=0"
        try:
            r = self.client.get(url, timeout=20)
            r.raise_for_status()
            root = ElementTree.fromstring(r.text)
        except Exception as e:  # network or XML parse
            logger.debug("nyaa fetch failed for %r: %s", query, e)
            return []

        items: List[dict] = []
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            info_hash = (it.findtext(f"{NYAA_NS}infoHash") or "").strip()
            if not title or not info_hash:
                continue
            gm = _GROUP_RE.search(title)
            rm = _RES_RE.search(title)
            is_batch = bool(_BATCH_RE.search(title))
            ep = None
            if not is_batch:
                em = _EP_RE.search(title)
                if em:
                    ep = em.group(1)
                    if ep.endswith(".0"):
                        ep = ep[:-2]
            try:
                seeders = int(it.findtext(f"{NYAA_NS}seeders") or "0")
            except ValueError:
                seeders = 0
            items.append(
                {
                    "title": title,
                    "hash": info_hash,
                    "seeders": seeders,
                    "group": gm.group(1) if gm else "",
                    "res": rm.group(1) if rm else None,
                    "ep": ep,
                    "batch": is_batch,
                }
            )
        return items

    def _items_for(self, query: str) -> List[dict]:
        """First query variant that yields parseable single-episode torrents."""
        for v in self._search_variants(query):
            items = self._fetch(v)
            if any(i["ep"] is not None for i in items):
                return items
        return []

    # ---- helpers -------------------------------------------------------
    @staticmethod
    def _magnet(info_hash: str, name: str) -> str:
        trackers = "".join(f"&tr={quote(t)}" for t in TRACKERS)
        return f"magnet:?xt=urn:btih:{info_hash}&dn={quote(name)}{trackers}"

    @staticmethod
    def _group_rank(group: str) -> int:
        for i, g in enumerate(PREFERRED_GROUPS):
            if g.lower() == group.lower():
                return i
        return len(PREFERRED_GROUPS)

    @staticmethod
    def _episodes(items: List[dict]) -> List[str]:
        return sorted(
            {i["ep"] for i in items if i["ep"]}, key=lambda x: float(x)
        )

    # ---- provider interface -------------------------------------------
    def search(self, params: "SearchParams") -> "SearchResults | None":
        items = self._items_for(params.query)
        eps = self._episodes(items)
        if not eps:
            return SearchResults(page_info=PageInfo(total=0), results=[])
        groups = sorted({i["group"] for i in items if i["group"]}, key=self._group_rank)
        label = groups[0] if groups else "nyaa"
        return SearchResults(
            page_info=PageInfo(total=1),
            results=[
                SearchResult(
                    id=params.query,
                    title=f"{params.query}  [nyaa · {label}]",
                    episodes=AnimeEpisodes(sub=eps),
                )
            ],
        )

    def get(self, params: "AnimeParams") -> "Anime | None":
        items = self._items_for(params.query or params.id)
        eps = self._episodes(items)
        return Anime(
            id=params.id,
            title=params.query or params.id,
            episodes=AnimeEpisodes(sub=eps),
            episodes_info=[AnimeEpisodeInfo(id=e, episode=e) for e in eps],
        )

    def episode_streams(
        self, params: "EpisodeStreamsParams"
    ) -> "Iterator[Server] | None":
        items = self._items_for(params.query or params.anime_id)
        try:
            want = float(params.episode)
        except (TypeError, ValueError):
            return None
        cands = [i for i in items if i["ep"] and float(i["ep"]) == want]
        if not cands:
            return None

        # rank: preferred group, then requested quality, then most seeders
        cands.sort(
            key=lambda i: (
                self._group_rank(i["group"]),
                0 if i["res"] == params.quality else 1,
                -i["seeders"],
            )
        )

        def _iter() -> "Iterator[Server]":
            for i in cands[:5]:
                quality = i["res"] if i["res"] in ("360", "480", "720", "1080") else "720"
                yield Server(
                    name=f"nyaa:{i['group'] or 'unknown'} ({i['seeders']} seeders)",
                    links=[
                        EpisodeStream(
                            link=self._magnet(i["hash"], i["title"]),
                            title=i["title"],
                            quality=quality,  # type: ignore[arg-type]
                            translation_type=MediaTranslationType.SUB,
                        )
                    ],
                    episode_title=i["title"],
                )

        return _iter()
