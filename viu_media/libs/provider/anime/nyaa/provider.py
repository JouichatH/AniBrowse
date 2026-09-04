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
import time
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

from .torrent import torrent_episodes

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
# Capturing form of _BATCH_RE: the first and last episode of the pack.
_BATCH_RANGE_RE = re.compile(r"[(\[]\s*0*(\d+)\s*[-~]\s*0*(\d+)\s*[)\]]")
# Season token inside a release OR AniList title: "S2", "Season 2",
# "2nd Season", "Part 2". (Not "S01E03": no word boundary between 1 and E.)
_SEASON_RE = re.compile(
    r"\b(?:S0*(\d{1,2})|Season\s*0*(\d{1,2})|(\d{1,2})(?:st|nd|rd|th)\s+Season"
    r"|Part\s*0*(\d{1,2}))\b",
    re.IGNORECASE,
)
# Trailing Roman-numeral season in an AniList base title ("Mushoku Tensei III").
_ROMAN_SEASON_RE = re.compile(r"\b(ii|iii|iv|v|vi)\s*$", re.IGNORECASE)
_ROMAN = {"ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6}

# Batch-range sanity: a "(1999-2023)" is a year span, not episodes, and a pack
# claiming more episodes than this is parsed garbage.
_MAX_BATCH_SPAN = 400
_YEAR_FLOOR = 1900

# A pack that declares itself complete but never spells the range out:
# "[EMBER] ... (Batch)", "... Complete Series", "[PHTMini] ... - S01 (BD ...)".
# These are the normal shape for a finished show, and the episode list lives in
# the torrent's file table rather than the title - see ``torrent.py``.
_PACK_HINT_RE = re.compile(
    r"\b(?:batch|complete(?:\s+series)?|(?:the\s+)?complete|seasons?\s*\d"
    r"|ultimate\s+collection|S0*\d{1,2}(?:\s*[-+~]\s*S0*\d{1,2})?)\b",
    re.IGNORECASE,
)
# A release that carries an English audio track as well as (or instead of) the
# Japanese one. Torrent releases are frequently dual-audio, so the SAME file
# serves sub and dub - the difference is only which audio track the player
# selects, which is why dub support here is about labelling and track choice
# rather than finding different torrents.
_DUAL_AUDIO_RE = re.compile(
    r"\b(?:dual[\s._-]*audio|multi[\s._-]*audio|multi|dual)\b", re.IGNORECASE
)
# An explicitly English-dubbed release (often no Japanese track at all).
_ENGLISH_DUB_RE = re.compile(
    r"\b(?:english[\s._-]*dub(?:bed)?|eng[\s._-]*dub(?:bed)?|dub(?:bed)?)\b",
    re.IGNORECASE,
)

# Releases dubbed/subbed into a language this app cannot help the user with.
# They are not dropped (they may be the only source) but they rank last.
_FOREIGN_RE = re.compile(
    r"\b(?:GERMAN|DEUTSCH|ITA(?:LIAN)?|SPA(?:NISH)?|CASTELLANO|LATINO|FRENCH"
    r"|VOSTFR|TRUEFRENCH|RUS(?:SIAN)?|POLISH|PT-?BR|PORTUGUES[E]?|TURKISH"
    r"|ARABIC|HINDI|THAI|VIETNAMESE)\b",
    re.IGNORECASE,
)

#: Appended to a title when the plain search returns only recent episodes.
#: nyaa's RSS shows the newest ~75 torrents, so a long-running show's back
#: catalogue is invisible until you ask for the packs by name.
_PACK_QUERY_SUFFIXES = ("Batch", "Complete")

#: How many season packs one lookup may open. Each is a ~100KB HTTPS GET, and
#: mirrored packs of the same show are common, so a few is plenty.
_MAX_PACK_PROBES = 3

#: Season packs whose file list we have already fetched, keyed by info hash.
#: A probe costs one ~100KB HTTPS GET, so never repeat one in a session.
_pack_cache: Dict["tuple[str, int]", List[str]] = {}
#: Packs whose probe failed - remembered so a dead link is not retried per menu.
#: Keyed like the cache, by (info hash, season).
_pack_failed: set = set()

# RSS response cache. One launch calls the provider several times over
# (search / get / episode_streams / neighbour prefetch), each of which
# re-queried nyaa for the SAME strings (~0.5s each, observed 2-4x per launch).
# 120s keeps a whole launch + its prefetches on one fetch per query while
# still noticing new uploads quickly.
_RSS_TTL = 120.0
_RSS_CACHE_MAX = 16
_rss_cache: Dict[str, "tuple[float, List[dict]]"] = {}

#: Magnet marker our provider appends to a *batch* torrent so the player knows
#: to stream just the requested episode's file out of the pack (webtorrent
#: ignores unknown magnet params). See mpv/player.py's batch handling.
BATCH_EP_PARAM = "x.aniep"
#: Season marker (``&x.anisn=1``). A pack can hold several seasons whose
#: episodes share numbers, so the episode alone is not enough to identify a
#: file - without this, "Season 1 + 2" packs played S02E02 for episode 2.
BATCH_SEASON_PARAM = "x.anisn"


def _fmt_ep(value: float) -> str:
    """Render an episode number without a trailing ``.0`` (7.0 -> "7")."""
    return str(int(value)) if float(value).is_integer() else str(value)


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
        root, season = base, None

        m = _ROMAN_SEASON_RE.search(base)
        m2 = re.search(
            r"\b(?:season\s*(\d+)|(\d+)(?:st|nd|rd|th)\s*season|part\s*(\d+))\b",
            title,
            re.IGNORECASE,
        )
        if m:
            season = _ROMAN[m.group(1).lower()]
            root = base[: m.start()].strip()
        elif m2:
            season = int(next(g for g in m2.groups() if g))
            root = re.split(r"\b(?:season|part)\b", base, flags=re.IGNORECASE)[0].strip()
            # "X 4th Season" leaves "X 4th" as the root; drop the ordinal so
            # queries become "X S4", not the unmatchable "X 4th S4".
            root = re.sub(
                r"\s+\d{1,2}(?:st|nd|rd|th)$", "", root, flags=re.IGNORECASE
            ).strip()

        variants: List[str] = []
        if season:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(season, "th")
            variants += [
                f"{root} S{season}",
                f"{root} Season {season}",
                # SubsPlease naming for many sequels ("... 4th Season").
                f"{root} {season}{suffix} Season",
            ]
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

    @staticmethod
    def _season_of(text: str) -> "int | None":
        """Season number a title claims, or None for an unmarked (first) season.

        Works for both AniList titles ("Mushoku Tensei III: ...", "X Season 2")
        and fansub release titles ("[SubsPlease] X S2 (01-10) ...").
        """
        base = text.split(": ")[0].strip()
        m = _ROMAN_SEASON_RE.search(base)
        if m:
            return _ROMAN[m.group(1).lower()]
        m2 = _SEASON_RE.search(text)
        if m2:
            return int(next(g for g in m2.groups() if g))
        return None

    # ---- nyaa fetch/parse ---------------------------------------------
    def _fetch(self, query: str) -> List[dict]:
        cached = _rss_cache.get(query.lower())
        if cached and time.monotonic() - cached[0] < _RSS_TTL:
            return cached[1]

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
            # nyaa's RSS <link> is a direct HTTPS .torrent download; carrying it
            # lets the player fetch metadata instantly instead of over DHT.
            link = (it.findtext("link") or "").strip()
            torrent_url = link if link.startswith("http") and link.endswith(".torrent") else None
            gm = _GROUP_RE.search(title)
            rm = _RES_RE.search(title)
            is_batch = bool(_BATCH_RE.search(title))
            ep = None
            batch_start = batch_end = None
            if is_batch:
                bm = _BATCH_RANGE_RE.search(title)
                if bm:
                    batch_start, batch_end = int(bm.group(1)), int(bm.group(2))
                if batch_start is None or batch_end is None:
                    batch_start = batch_end = None
                elif (
                    batch_start > batch_end
                    or batch_end >= _YEAR_FLOOR  # "(1999-2023)" is a year span
                    or batch_end - batch_start + 1 > _MAX_BATCH_SPAN
                ):
                    batch_start = batch_end = None
            else:
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
                    "batch_start": batch_start,
                    "batch_end": batch_end,
                    "torrent_url": torrent_url,
                    # A complete-season pack whose title hides the range. Its
                    # episode list is read from the .torrent, but only if the
                    # cheap paths above find nothing - see _pack_episodes.
                    "pack": bool(
                        ep is None
                        and batch_start is None
                        and torrent_url
                        and _PACK_HINT_RE.search(title)
                    ),
                    "foreign": bool(_FOREIGN_RE.search(title)),
                    # Whether this release can serve an English dub at all.
                    # MULTi/Dual releases keep both tracks, so they serve sub
                    # AND dub; an "[English Dub]" release usually serves dub
                    # only. Both are recorded so the menu can offer dub and the
                    # ranking can prefer the right file.
                    "dual_audio": bool(_DUAL_AUDIO_RE.search(title)),
                    "dub_only": bool(
                        _ENGLISH_DUB_RE.search(title)
                        and not _DUAL_AUDIO_RE.search(title)
                    ),
                }
            )
        if len(_rss_cache) >= _RSS_CACHE_MAX:
            _rss_cache.pop(min(_rss_cache, key=lambda k: _rss_cache[k][0]))
        _rss_cache[query.lower()] = (time.monotonic(), items)
        return items

    def _probe_pack(self, item: dict, wanted_season: int = 1) -> List[str]:
        """Episode numbers inside one season pack, by reading its .torrent."""
        key = (item["hash"], wanted_season)
        if key in _pack_cache:
            return _pack_cache[key]
        if key in _pack_failed or not item.get("torrent_url"):
            return []
        try:
            r = self.client.get(item["torrent_url"], timeout=20)
            r.raise_for_status()
            episodes = torrent_episodes(r.content, wanted_season)
        except Exception as e:  # noqa: BLE001 - a dead link must not break the menu
            logger.debug("nyaa pack probe failed for %r: %s", item["title"][:60], e)
            _pack_failed.add(key)
            return []
        if not episodes:
            _pack_failed.add(key)
            return []
        logger.debug(
            "nyaa pack %r -> %d episodes", item["title"][:60], len(episodes)
        )
        _pack_cache[key] = episodes
        return episodes

    @staticmethod
    def _pack_rank(item: dict) -> tuple:
        """Best pack first: our language, known group, most seeders."""
        return (
            1 if item.get("foreign") else 0,
            Nyaa._group_rank(item.get("group") or ""),
            -item.get("seeders", 0),
        )

    def _packs_with_episodes(
        self, items: List[dict], wanted_season: int = 1
    ) -> List[dict]:
        """Probe the most promising packs, annotating them with their episodes.

        Bounded to a handful of fetches: a show with twenty mirrored packs must
        not turn one menu open into twenty HTTPS round trips.
        """
        packs = sorted(
            (i for i in items if i.get("pack")), key=self._pack_rank
        )[:_MAX_PACK_PROBES]
        probed = []
        for pack in packs:
            episodes = self._probe_pack(pack, wanted_season)
            if episodes:
                pack = {**pack, "pack_episodes": episodes, "season": wanted_season}
                probed.append(pack)
        return probed

    @staticmethod
    def _episode_candidates(items: List[dict], want: float) -> "tuple[List[dict], bool]":
        """(candidates, is_batch) for one episode: single-episode torrents
        first; only if none exist, season batches that cover the number."""
        singles = [i for i in items if i["ep"] and float(i["ep"]) == want]
        if singles:
            return singles, False
        if want.is_integer():
            batches = [
                i
                for i in items
                if i.get("batch_start") and i["batch_start"] <= want <= i["batch_end"]
            ]
            if batches:
                return batches, True
        # Packs probed from their .torrent carry an explicit episode list.
        probed = [
            i
            for i in items
            if any(float(e) == want for e in i.get("pack_episodes") or ())
        ]
        if probed:
            return probed, True
        return [], False

    def _targeted_items(self, query: str, want: float) -> List[dict]:
        """Episode-targeted queries for an episode missing from the generic search.

        The title search only sees nyaa's newest ~75 results, so a back-catalog
        episode of a long or completed show (whose single-episode uploads are
        months old) falls off the first page even though nyaa still has it.
        Appending the zero-padded episode number ("<title> 03") surfaces those
        releases directly.
        """
        wanted = self._season_of(query) or 1
        term = f"{int(want):02d}" if want.is_integer() else _fmt_ep(want)
        for v in self._search_variants(query):
            items = [
                i
                for i in self._fetch(f"{v} {term}")
                if (self._season_of(i["title"]) or 1) == wanted
            ]
            if self._episode_candidates(items, want)[0]:
                return items
        return []

    def _items_for(self, query: str) -> List[dict]:
        """First query variant that yields usable torrents of the RIGHT season.

        nyaa's search is a fuzzy substring match, so a query for a season-less
        title ("Sousou no Frieren") also returns other seasons' releases
        ("... S2 (01-10)"), which cover the same episode NUMBERS as the wanted
        season - picking one would play a different season's episode. Items
        whose title claims a different season than the query are dropped (an
        unmarked title counts as season 1 on both sides).

        Prefers a variant with single-episode releases (airing simulcasts); a
        completed / back-catalog show is often only on nyaa as a season batch,
        so a variant that yields only batch packs is accepted too.
        """
        wanted = self._season_of(query) or 1
        fallback: List[dict] = []
        for v in self._search_variants(query):
            items = [
                i
                for i in self._fetch(v)
                if (self._season_of(i["title"]) or 1) == wanted
            ]
            cheap = self._episodes(items)
            if cheap and self._looks_complete(cheap):
                # A clean run from episode 1: the simulcast releases cover the
                # show, so charge nothing for opening season packs.
                return items
            if items and (cheap or any(i.get("pack") for i in items)):
                # Either nothing names an episode (a finished show, pack-only)
                # or the run is partial - nyaa's first page only holds ~75 of
                # the newest torrents, so a long-running show shows up as
                # "1100-1176". Season packs hold the rest; read them.
                fallback = fallback or items
        # Still nothing usable: ask nyaa for the packs explicitly.
        if not any(i.get("pack") for i in fallback):
            for v in self._search_variants(query):
                found = False
                for suffix in _PACK_QUERY_SUFFIXES:
                    extra = [
                        i
                        for i in self._fetch(f"{v} {suffix}")
                        if (self._season_of(i["title"]) or 1) == wanted
                        and (i.get("pack") or i.get("batch_start"))
                    ]
                    if extra:
                        fallback = fallback + extra
                        found = True
                        break
                if found:
                    break

        if fallback:
            probed = self._packs_with_episodes(fallback, wanted)
            if probed:
                return [i for i in fallback if not i.get("pack")] + probed
            return fallback
        return []

    @staticmethod
    def _looks_complete(episodes: List[str]) -> bool:
        """Whether an episode list is a gapless run starting at episode 1.

        Anything else - starting at 1100, or 5 then 46 - means nyaa's first
        page showed only part of the show and the rest is inside a season pack.
        """
        if not episodes:
            return False
        numbers = sorted(float(e) for e in episodes)
        if numbers[0] > 1:
            return False
        whole = [n for n in numbers if float(n).is_integer()]
        if len(whole) < 2:
            return len(numbers) >= 2
        return whole[-1] - whole[0] + 1 == len(whole)

    # ---- helpers -------------------------------------------------------
    @staticmethod
    def _magnet(
        info_hash: str,
        name: str,
        select_ep: "str | None" = None,
        torrent_url: "str | None" = None,
        select_season: "int | None" = None,
    ) -> str:
        trackers = "".join(f"&tr={quote(t)}" for t in TRACKERS)
        # xs (standard magnet param) = exact source of the .torrent file; both
        # our player and webtorrent use it to skip the slow DHT metadata fetch.
        xs = f"&xs={quote(torrent_url, safe='')}" if torrent_url else ""
        marker = f"&{BATCH_EP_PARAM}={select_ep}" if select_ep is not None else ""
        if select_ep is not None and select_season is not None:
            marker += f"&{BATCH_SEASON_PARAM}={select_season}"
        return f"magnet:?xt=urn:btih:{info_hash}&dn={quote(name)}{trackers}{xs}{marker}"

    @staticmethod
    def _group_rank(group: str) -> int:
        for i, g in enumerate(PREFERRED_GROUPS):
            if g.lower() == group.lower():
                return i
        return len(PREFERRED_GROUPS)

    @staticmethod
    def _dub_items(items: List[dict]) -> List[dict]:
        """Releases that can play with an English audio track."""
        return [i for i in items if i.get("dual_audio") or i.get("dub_only")]

    @staticmethod
    def _episodes(items: List[dict]) -> List[str]:
        """Every episode number the show exposes on nyaa.

        Single-episode torrents contribute their own number; a season batch
        ``(01-28)`` contributes each integer in its range, so a completed show
        that is only available as a pack still gets a full episode menu.
        """
        eps: set = {i["ep"] for i in items if i.get("ep")}
        for i in items:
            start, end = i.get("batch_start"), i.get("batch_end")
            if start and end:
                eps.update(str(n) for n in range(start, end + 1))
        for i in items:
            eps.update(i.get("pack_episodes") or ())
        return sorted(eps, key=lambda x: float(x))

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
                    episodes=AnimeEpisodes(
                        sub=eps, dub=self._episodes(self._dub_items(items))
                    ),
                )
            ],
        )

    def get(self, params: "AnimeParams") -> "Anime | None":
        items = self._items_for(params.query or params.id)
        eps = self._episodes(items)
        # Dual-audio releases serve both, so an episode can appear in both
        # lists; the menu asks for whichever the config wants.
        dub_eps = self._episodes(self._dub_items(items))
        return Anime(
            id=params.id,
            title=params.query or params.id,
            episodes=AnimeEpisodes(sub=eps, dub=dub_eps),
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

        # Prefer a single-episode torrent (smaller, faster). Only if none exists
        # for this episode do we fall back to a season batch that covers it -
        # completed shows are frequently batch-only on nyaa. The batch magnet is
        # tagged so the player streams just this episode's file out of the pack.
        want_dub = str(getattr(params, "translation_type", "sub")).lower().endswith(
            "dub"
        )
        if want_dub:
            # Only releases that actually carry an English track can serve a
            # dub. If none do, fall through to everything rather than failing:
            # the menu already told the user which episodes have a dub.
            dub_items = self._dub_items(items)
            if dub_items:
                items = dub_items

        cands, is_batch = self._episode_candidates(items, want)
        if not cands:
            # Not on the first page of the generic search - query the episode
            # number directly before giving up.
            cands, is_batch = self._episode_candidates(
                self._targeted_items(params.query or params.anime_id, want), want
            )
        if not cands:
            return None

        # rank: preferred group, then requested quality, then most seeders
        cands.sort(
            key=lambda i: (
                # When dub is wanted, a release carrying an English track wins
                # over a better-ranked group that cannot serve one at all.
                0 if (not want_dub or i.get("dual_audio") or i.get("dub_only")) else 1,
                # For sub, a dub-only release is the last resort - it may have
                # no Japanese audio to switch back to.
                1 if (not want_dub and i.get("dub_only")) else 0,
                self._group_rank(i["group"]),
                0 if i["res"] == params.quality else 1,
                -i["seeders"],
            )
        )

        select_ep = _fmt_ep(want) if is_batch else None
        # The season the query asked for, so the player can tell S01E02 from
        # S02E02 inside a multi-season pack.
        select_season = (
            self._season_of(params.query or params.anime_id) or 1
        ) if is_batch else None
        tag = " batch" if is_batch else ""

        def _iter() -> "Iterator[Server]":
            for i in cands[:5]:
                quality = i["res"] if i["res"] in ("360", "480", "720", "1080") else "720"
                yield Server(
                    name=(
                        f"nyaa:{i['group'] or 'unknown'}{tag}"
                        f"{' dub' if want_dub else ''} ({i['seeders']} seeders)"
                    ),
                    links=[
                        EpisodeStream(
                            link=self._magnet(
                                i["hash"],
                                i["title"],
                                select_ep,
                                i.get("torrent_url"),
                                select_season,
                            ),
                            title=i["title"],
                            quality=quality,  # type: ignore[arg-type]
                            translation_type=(
                                MediaTranslationType.DUB
                                if want_dub
                                else MediaTranslationType.SUB
                            ),
                        )
                    ],
                    episode_title=i["title"],
                )

        return _iter()
