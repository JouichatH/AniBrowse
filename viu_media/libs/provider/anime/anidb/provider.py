"""anidb.app streaming provider for ani-browse.

Why this exists: allanime/mkissa went behind a captcha wall for good (its API
answers with empty or ``AA_CRYPTO_STALE`` payloads no matter how fresh the
signing key is, and the browser fallback dies at Cloudflare). ani-cli reached
the same dead end and shipped v5.0.0 with allanime removed in favour of
anidb.app, so this provider follows them.

The appeal of anidb.app is that there is nothing to reverse-engineer: no signed
handshake, no rotating key/epoch treadmill, no headless browser, no captcha.
Four plain requests get from a title to an HLS master playlist::

    browse?q=<query>                      -> HTML cards: <slug>-<id> + title
    api/frontend/anime/<id>/episodes      -> JSON: [{id, number, filler}, ...]
    api/frontend/episode/<epid>/languages -> JSON: [{code: jpn|eng, embed_url}]
    <embed_url>                           -> HTML with  file: '<master.m3u8>'

Two quirks of the source drive the code below:

1. **Episode numbering is inconsistent.** Some entries number a sequel from 1
   (Mushoku Tensei S2 = 1-12), others continue absolutely from the previous
   season (Frieren S2 = 29-38, Slime S2 Part 2 = 37-48). AniList, the local
   registry and the nyaa fallback all use per-entry numbering, so this provider
   normalises every entry to start at 1 and keeps the mapping back to the real
   anidb episode id internally. See ``_episode_index``.
2. **Dub availability is only knowable per episode.** The languages endpoint is
   the sole source of truth and costs one request per episode, so the episode
   list is offered for both sub and dub; an episode with no ``eng`` track simply
   yields no servers, which drops through to the nyaa fallback like any other
   miss.
"""

from __future__ import annotations

import html
import logging
import re
import time
from typing import TYPE_CHECKING, ClassVar, Dict, List
from urllib.parse import quote

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

ANIDB_URL = "https://anidb.app"
SEARCH_URL = ANIDB_URL + "/browse?q={}"
EPISODES_API = ANIDB_URL + "/api/frontend/anime/{}/episodes"
LANGUAGES_API = ANIDB_URL + "/api/frontend/episode/{}/languages"

TIMEOUT = 20.0

#: Language code anidb uses per translation type.
_LANG_CODE = {"sub": "jpn", "dub": "eng"}

# A search card is an <a> whose href is /anime/<slug>-<id>; the anchor's own
# title= attribute carries the clean show title (the <img alt=> repeats it).
_CARD_ID_RE = re.compile(r'/anime/([a-z0-9-]+-\d+)"', re.I)
_CARD_TITLE_RE = re.compile(r'title="([^"]*)"')
_CARD_POSTER_RE = re.compile(r'<img[^>]+src="(https?://[^"]+)"')
_CARD_TYPE_RE = re.compile(r'class="badge badge-orange[^"]*"[^>]*>\s*([A-Za-z]+)\s*<')
# Cloudflare's interstitial, which replaces the page body entirely.
_CHALLENGE_RE = re.compile(r"Just a moment|cf-browser-verification|__cf_chl", re.I)

# The embed page hands the player its master playlist as  file: '<url>'
_EMBED_FILE_RE = re.compile(r"file:\s*'([^']+)'")
# A variant line in the master playlist, plus the URL on the line after it.
# I-FRAME variants carry their URL inline as URI="..." so they never match.
_VARIANT_RE = re.compile(
    r"#EXT-X-STREAM-INF:[^\r\n]*RESOLUTION=\d+x(\d+)[^\r\n]*\r?\n\s*(\S+)"
)

#: Qualities the rest of the app understands (EpisodeStream.quality).
_QUALITIES = (360, 480, 720, 1080)

# Episode lists are re-read constantly: once for the menu, then again for the
# played episode and each prefetched neighbour. 300s keeps a whole viewing
# session on one fetch (One Piece's list is ~1200 entries) while still picking
# up a newly aired episode within a few minutes.
_EPISODES_TTL = 300.0
_EPISODES_CACHE_MAX = 8
_episodes_cache: Dict[str, "tuple[float, List[dict]]"] = {}


def _fmt_ep(value: float) -> str:
    """Render an episode number without a trailing ``.0`` (7.0 -> "7")."""
    return str(int(value)) if float(value).is_integer() else str(value)


def _nearest_quality(height: int) -> str:
    """Map a stream height onto the closest quality the app supports."""
    return str(min(_QUALITIES, key=lambda q: abs(q - height)))


class AniDB(BaseAnimeProvider):
    # anidb.app sits behind Cloudflare. A real desktop Chrome UA passes today;
    # the factory's random UA does not always, so pin one here (HEADERS wins
    # over the factory's default).
    HEADERS: ClassVar[Dict[str, str]] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    # ---- fetch helpers -------------------------------------------------
    def _get(self, url: str) -> "str | None":
        """GET a URL as text, retrying once on a transient failure.

        anidb's HLS edge answers an occasional 502; one retry turns that from a
        failed episode into a hiccup.
        """
        for attempt in (1, 2):
            try:
                r = self.client.get(url, timeout=TIMEOUT, follow_redirects=True)
                r.raise_for_status()
                return r.text
            except Exception as e:  # noqa: BLE001 - network/HTTP, never fatal
                if attempt == 2:
                    logger.debug("anidb fetch failed for %s: %s", url, e)
                    return None
                time.sleep(0.4)
        return None

    def _get_json(self, url: str) -> "dict | list | None":
        try:
            r = self.client.get(url, timeout=TIMEOUT, follow_redirects=True)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            logger.debug("anidb json fetch failed for %s: %s", url, e)
            return None

    @staticmethod
    def _numeric_id(anime_id: str) -> str:
        """``frieren-beyond-journeys-end-1663`` -> ``1663``.

        The episodes endpoint keys off the trailing numeric id, not the slug.
        """
        return anime_id.rsplit("-", 1)[-1]

    # ---- episode list ---------------------------------------------------
    def _episodes_payload(self, anime_id: str) -> List[dict]:
        """Raw episode dicts for a show, cached."""
        key = anime_id.lower()
        cached = _episodes_cache.get(key)
        if cached and time.monotonic() - cached[0] < _EPISODES_TTL:
            return cached[1]

        data = self._get_json(EPISODES_API.format(self._numeric_id(anime_id)))
        episodes: List[dict] = []
        if isinstance(data, dict):
            raw = data.get("episodes")
            if isinstance(raw, list):
                episodes = [
                    e
                    for e in raw
                    if isinstance(e, dict)
                    and e.get("id") is not None
                    and isinstance(e.get("number"), (int, float))
                ]

        if len(_episodes_cache) >= _EPISODES_CACHE_MAX:
            _episodes_cache.pop(min(_episodes_cache, key=lambda k: _episodes_cache[k][0]))
        _episodes_cache[key] = (time.monotonic(), episodes)
        return episodes

    def _episode_index(self, anime_id: str) -> "Dict[str, int]":
        """Map the episode numbers we show -> anidb's internal episode id.

        anidb numbers some sequels absolutely (Frieren S2 is 29-38) and others
        from 1 (Mushoku Tensei S2 is 1-12). Everything downstream - AniList
        progress, the watch registry, the nyaa fallback - counts from 1 within a
        season, so an entry that starts above 1 is shifted down by a constant.
        Entries starting at 0 or 1 are left exactly as they are, which keeps
        episode-0 specials and absolute long-runners (One Piece) untouched.
        """
        episodes = self._episodes_payload(anime_id)
        if not episodes:
            return {}

        numbers = sorted(float(e["number"]) for e in episodes)
        first = numbers[0]
        offset = first - 1 if first > 1 else 0.0
        if offset:
            logger.debug(
                "anidb %s numbers episodes %s-%s; shifting down by %s",
                anime_id,
                _fmt_ep(first),
                _fmt_ep(numbers[-1]),
                _fmt_ep(offset),
            )

        index: Dict[str, int] = {}
        for e in episodes:
            # round() keeps 24.9 - 23.9 from landing on 1.0000000000000018.
            shown = round(float(e["number"]) - offset, 3)
            index[_fmt_ep(shown)] = int(e["id"])
        return index

    def _episode_numbers(self, anime_id: str) -> List[str]:
        return sorted(self._episode_index(anime_id), key=float)

    # ---- search ---------------------------------------------------------
    @staticmethod
    def _parse_cards(page: str) -> List[dict]:
        """Pull (id, title, poster, type) out of a browse page."""
        results: List[dict] = []
        seen: set = set()
        # Cards are anchors; splitting on them lets each card's title/img/badge
        # be matched locally instead of racing across the whole document.
        for chunk in page.replace("\n", " ").split("<a ")[1:]:
            m = _CARD_ID_RE.search(chunk)
            if not m or m.group(1) in seen:
                continue
            t = _CARD_TITLE_RE.search(chunk)
            if not t:
                continue
            seen.add(m.group(1))
            poster = _CARD_POSTER_RE.search(chunk)
            media_type = _CARD_TYPE_RE.search(chunk)
            results.append(
                {
                    "id": m.group(1),
                    "title": html.unescape(t.group(1)).strip(),
                    "poster": poster.group(1) if poster else None,
                    "type": media_type.group(1) if media_type else None,
                }
            )
        return results

    def search(self, params: "SearchParams") -> "SearchResults | None":
        page = self._get(SEARCH_URL.format(quote(params.query)))
        if page is None:
            return None
        if _CHALLENGE_RE.search(page):
            # Nothing we can do with plain httpx; a TLS-impersonating client
            # (curl_cffi) would be the next step if this becomes common.
            logger.error(
                "anidb.app is serving a Cloudflare challenge - streams "
                "unavailable from this network/IP right now"
            )
            return None

        cards = self._parse_cards(page)
        # Episode lists cost one request each, and nothing reads them off a
        # search result (the flow always calls get() on the chosen show), so
        # they stay empty here and are filled in by get().
        return SearchResults(
            page_info=PageInfo(total=len(cards), current_page=1),
            results=[
                SearchResult(
                    id=c["id"],
                    title=c["title"],
                    episodes=AnimeEpisodes(sub=[]),
                    media_type=c["type"],
                    poster=c["poster"],
                )
                for c in cards
            ],
        )

    # ---- details --------------------------------------------------------
    def get(self, params: "AnimeParams") -> "Anime | None":
        numbers = self._episode_numbers(params.id)
        if not numbers:
            logger.debug("anidb returned no episodes for %s", params.id)
            return None

        # Dub availability is per episode and only visible from the languages
        # endpoint, so both lists are offered; a missing dub surfaces as "no
        # servers" at stream time and falls through to nyaa.
        return Anime(
            id=params.id,
            title=params.query or params.id,
            episodes=AnimeEpisodes(sub=numbers, dub=numbers),
            episodes_info=[AnimeEpisodeInfo(id=n, episode=n) for n in numbers],
        )

    # ---- streams --------------------------------------------------------
    def _embed_url(self, episode_id: int, translation_type: str) -> "str | None":
        data = self._get_json(LANGUAGES_API.format(episode_id))
        languages = data.get("languages") if isinstance(data, dict) else None
        if not isinstance(languages, list):
            return None
        want = _LANG_CODE.get(translation_type, "jpn")
        for lang in languages:
            if isinstance(lang, dict) and lang.get("code") == want:
                url = lang.get("embed_url")
                return url if isinstance(url, str) and url else None
        logger.debug(
            "anidb episode %s has no %r track (has: %s)",
            episode_id,
            want,
            [x.get("code") for x in languages if isinstance(x, dict)],
        )
        return None

    def _variants(self, embed_url: str) -> "List[tuple[str, str]]":
        """(quality, url) for every rendition in the episode's master playlist."""
        embed_page = self._get(embed_url)
        if not embed_page:
            return []
        m = _EMBED_FILE_RE.search(embed_page)
        if not m:
            logger.debug("anidb embed page carried no master playlist: %s", embed_url)
            return []

        master_url = m.group(1)
        master = self._get(master_url)
        if not master:
            return []

        variants = [
            (_nearest_quality(int(height)), url)
            for height, url in _VARIANT_RE.findall(master)
        ]
        if not variants:
            # A single-rendition upload has no variant lines; the master URL is
            # itself playable.
            return [("720", master_url)]
        # Best first: some call sites (player IPC, prefetch) take links[0]
        # directly rather than filtering by the configured quality.
        variants.sort(key=lambda v: int(v[0]), reverse=True)
        return variants

    def episode_streams(
        self, params: "EpisodeStreamsParams"
    ) -> "Iterator[Server] | None":
        index = self._episode_index(params.anime_id)
        try:
            wanted = _fmt_ep(float(params.episode))
        except (TypeError, ValueError):
            return None

        episode_id = index.get(wanted)
        if episode_id is None:
            logger.debug(
                "anidb has no episode %s for %s", params.episode, params.anime_id
            )
            return None

        embed_url = self._embed_url(episode_id, params.translation_type)
        if not embed_url:
            return None

        variants = self._variants(embed_url)
        if not variants:
            return None

        translation = (
            MediaTranslationType.DUB
            if params.translation_type == "dub"
            else MediaTranslationType.SUB
        )
        title = f"Episode {wanted}"

        def _iter() -> "Iterator[Server]":
            yield Server(
                name="anidb",
                links=[
                    EpisodeStream(
                        link=url,
                        title=title,
                        quality=quality,  # type: ignore[arg-type]
                        translation_type=translation,
                        format="hls",
                        hls=True,
                    )
                    for quality, url in variants
                ],
                episode_title=title,
                # The CDN serves these without any auth today; sending the
                # origin's own Referer/UA keeps working if it starts checking.
                headers={"Referer": ANIDB_URL + "/", **self.HEADERS},
                audio=["jpn" if translation is MediaTranslationType.SUB else "eng"],
            )

        return _iter()
