"""Turn anidb.app catalogue pages into the app's generic media model.

Two shapes are parsed:

* **browse cards** - cheap, one request for a whole page (~28 shows). They carry
  id, title, poster, media type and score. Enough to render a results list.
* **detail pages** - one request per show, used to fill in the synopsis, genres,
  romaji title and MAL id that cards omit. anidb ships a JSON-LD ``TVSeries``
  block which is far steadier than scraping markup, but it is *not valid JSON*:
  the site HTML-escapes apostrophes and leaves the backslash in front, producing
  ``\\&#039;``. ``_loads_jsonld`` repairs that before parsing.
"""

from __future__ import annotations

import html
import json
import logging
import re
from typing import Any, Dict, List, Optional

from ..types import (
    MediaFormat,
    MediaGenre,
    MediaImage,
    MediaItem,
    MediaSearchResult,
    MediaStatus,
    MediaTitle,
    PageInfo,
)

logger = logging.getLogger(__name__)

# A catalogue card: an <a> to /anime/<slug>-<id> carrying the title in its own
# title= attribute, the poster as the first <img>, and a type badge.
_CARD_ID_RE = re.compile(r"/anime/([a-z0-9-]+-\d+)\"", re.I)
_CARD_TITLE_RE = re.compile(r'title="([^"]*)"')
_CARD_POSTER_RE = re.compile(r'<img[^>]+src="(https?://[^"]+)"')
_CARD_TYPE_RE = re.compile(r'class="badge badge-orange[^"]*"[^>]*>\s*([A-Za-z]+)\s*<')

_JSONLD_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.S | re.I
)
_MAL_RE = re.compile(r"myanimelist\.net/anime/(\d+)")
_STATUS_RE = re.compile(r"(Currently Airing|Finished Airing|Not yet aired)", re.I)
# NOTE: no episode count is scraped. The detail page has no dedicated field for
# it, and the nearest-looking text ("3 episodes", from a recent-episodes widget)
# gave One Piece 3 episodes. The episode LIST comes from the provider, which is
# authoritative, so leaving this None is both simpler and correct.

# Cloudflare's interstitial replaces the page body entirely.
_CHALLENGE_RE = re.compile(r"Just a moment|cf-browser-verification|__cf_chl", re.I)
# Backslashes that are not a legal JSON escape (anidb emits a stray one).
_BAD_ESCAPE_RE = re.compile(r'\\(?!["\\/bfnrtu])')
# Pagination hrefs arrive HTML-escaped ("...&amp;page=2"), so the separator
# before "page" may be "?", "&" or the tail of "&amp;".
_PAGE_RE = re.compile(r"(?:\?|&|&amp;)page=(\d+)")

_ANIDB_TYPES = {
    "TV": MediaFormat.TV,
    "Movie": MediaFormat.MOVIE,
    "OVA": MediaFormat.OVA,
    "ONA": MediaFormat.ONA,
    "Special": MediaFormat.SPECIAL,
    "Music": MediaFormat.MUSIC,
}

_ANIDB_STATUS = {
    "currently airing": MediaStatus.RELEASING,
    "finished airing": MediaStatus.FINISHED,
    "not yet aired": MediaStatus.NOT_YET_RELEASED,
}

#: Genre names our MediaGenre enum accepts. anidb carries a wider list
#: ("Award Winning", "Suspense", "Gourmet", ...) which would raise inside the
#: pydantic model and lose the whole page, so unknown names are dropped.
_KNOWN_GENRES = {g.value for g in MediaGenre}


def numeric_id(anime_id: str) -> int:
    """``frieren-beyond-journeys-end-1663`` -> ``1663``.

    anidb's trailing number is stable and unique per entry, which makes it a
    sound primary key for the watch registry.
    """
    tail = anime_id.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def is_challenged(page: str) -> bool:
    return bool(_CHALLENGE_RE.search(page))


def _loads_jsonld(page: str) -> Dict[str, Any]:
    """The detail page's JSON-LD block, repaired enough to parse."""
    match = _JSONLD_RE.search(page)
    if not match:
        return {}
    raw = _BAD_ESCAPE_RE.sub("", html.unescape(match.group(1)))
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError) as e:
        logger.debug("anidb JSON-LD unparseable: %s", e)
        return {}


def _genres(names) -> List[MediaGenre]:
    out = []
    for name in names or []:
        if isinstance(name, str) and name in _KNOWN_GENRES:
            out.append(name)
    return [MediaGenre(n) for n in dict.fromkeys(out)]


def parse_cards(page: str) -> List[dict]:
    """Every catalogue card on a browse/search page, in the site's own order."""
    results: List[dict] = []
    seen: set = set()
    # Splitting on anchors keeps each card's title/img/badge matched locally
    # instead of racing across the whole document.
    for chunk in page.replace("\n", " ").split("<a ")[1:]:
        m = _CARD_ID_RE.search(chunk)
        if not m or m.group(1) in seen:
            continue
        title = _CARD_TITLE_RE.search(chunk)
        if not title:
            continue
        seen.add(m.group(1))
        poster = _CARD_POSTER_RE.search(chunk)
        media_type = _CARD_TYPE_RE.search(chunk)
        results.append(
            {
                "slug": m.group(1),
                "title": html.unescape(title.group(1)).strip(),
                "poster": poster.group(1) if poster else None,
                "type": media_type.group(1) if media_type else None,
            }
        )
    return results


def card_to_media_item(card: dict) -> Optional[MediaItem]:
    """A MediaItem from card data alone (no detail request)."""
    mid = numeric_id(card["slug"])
    if not mid:
        return None
    try:
        return MediaItem(
            id=mid,
            title=MediaTitle(english=card["title"], romaji=card["title"]),
            cover_image=MediaImage(large=card.get("poster") or ""),
            format=_ANIDB_TYPES.get(card.get("type") or ""),
            streaming_episodes={},
            user_status=None,
        )
    except Exception as e:  # noqa: BLE001 - one bad card must not lose the page
        logger.debug("skipping unmappable anidb card %s: %s", card.get("slug"), e)
        return None


def enrich_from_detail(item: MediaItem, page: str) -> MediaItem:
    """Fold a detail page's metadata into a card-derived MediaItem.

    Best-effort by design: the results list is already usable without it, so a
    failed or unrecognised detail page returns the original item untouched.
    """
    data = _loads_jsonld(page)
    flat = page.replace("\n", " ")

    # Only fields actually found on the page are written, so a page we cannot
    # read leaves the card-derived item exactly as it was.
    update: Dict[str, Any] = {}

    romaji = data.get("alternateName")
    english = data.get("name")
    if romaji or english:
        update["title"] = MediaTitle(
            english=english or item.title.english,
            romaji=romaji or item.title.romaji,
            native=item.title.native,
        )
        # The romaji title is a second thing to try when the provider search
        # finds nothing under the English one.
        extra = [t for t in (romaji, english) if t and t != item.title.english]
        if extra:
            update["synonymns"] = list(dict.fromkeys([*item.synonymns, *extra]))

    if data.get("description"):
        update["description"] = data["description"]

    genres = _genres(data.get("genre"))
    if genres:
        update["genres"] = genres

    mal = _MAL_RE.search(flat)
    if mal:
        update["id_mal"] = int(mal.group(1))

    status = _STATUS_RE.search(flat)
    if status and status.group(1).lower() in _ANIDB_STATUS:
        update["status"] = _ANIDB_STATUS[status.group(1).lower()]

    if not update:
        return item
    try:
        return item.model_copy(update=update)
    except Exception as e:  # noqa: BLE001 - enrichment is optional
        logger.debug("anidb detail enrichment failed for %s: %s", item.id, e)
        return item


def to_search_result(page: str, current_page: int = 1) -> Optional[MediaSearchResult]:
    """Map a browse/search page into a results set, or None if unusable."""
    if is_challenged(page):
        logger.error(
            "anidb.app is serving a Cloudflare challenge - browsing unavailable "
            "from this network/IP right now"
        )
        return None

    cards = parse_cards(page)
    media = [m for m in (card_to_media_item(c) for c in cards) if m]

    # anidb paginates with plain ?page=N links; a link past the current page
    # means there is more to show.
    pages = {int(n) for n in _PAGE_RE.findall(page.replace("\n", " "))}
    has_next = any(p > current_page for p in pages)

    return MediaSearchResult(
        page_info=PageInfo(
            total=len(media),
            current_page=current_page,
            has_next_page=has_next,
            per_page=len(media) or 28,
        ),
        media=media,
    )


def slugs_for(page: str) -> List[str]:
    """Card slugs in page order, for pairing detail fetches with results."""
    return [c["slug"] for c in parse_cards(page)]
