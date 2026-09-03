"""anidb.app as a media/browse backend.

Why this exists: browsing used to depend on a metadata service that has nothing
to do with playback, so an outage there took the whole app down while every
stream was still perfectly reachable. On 2026-08-02 both candidates failed at
once - AniList disabled its API outright, and Jikan degraded to serving only
cached URLs - leaving no working browse path at all.

This backend removes that class of failure by browsing the *same* host that
serves the streams. anidb.app's ``/browse`` is a real catalogue: it sorts by
trending / popularity / rating / favourites / recency and filters by type,
status, season, year and genre, which covers every menu the app offers. If
browsing is down here, playback was down anyway - the two can no longer fail
independently.

Trade-off: MyAnimeList/AniList account features (list sync, scores, progress
push) do not exist here. The app's personal lists are local-first and keep
working; a user who wants their AniList list synced can still select the
anilist backend when it is healthy.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, List, Optional
from urllib.parse import urlencode

from ..base import BaseApiClient
from ..types import (
    AiringScheduleResult,
    CharacterSearchResult,
    MediaItem,
    MediaReview,
    MediaSearchResult,
    MediaSort,
    MediaStatus,
    Notification,
    UserProfile,
)
from . import mapper

if TYPE_CHECKING:
    from ..params import (
        MediaAiringScheduleParams,
        MediaCharactersParams,
        MediaRecommendationParams,
        MediaRelationsParams,
        MediaReviewsParams,
        MediaSearchParams,
        UpdateUserMediaListEntryParams,
        UserMediaListSearchParams,
    )

logger = logging.getLogger(__name__)

ANIDB_URL = "https://anidb.app"
BROWSE_URL = ANIDB_URL + "/browse"
DETAIL_URL = ANIDB_URL + "/anime/{}"

TIMEOUT = 20.0

#: How many detail pages to fetch at once when enriching a results page.
#: 28 cards enrich in well under a second at this width, with no rate limiting.
_ENRICH_WORKERS = 16

# The app's sorts onto anidb's. anidb's own vocabulary lines up almost exactly
# with the menus, which is why every category stays distinct.
_SORTS = {
    MediaSort.TRENDING_DESC: "order_trending",
    MediaSort.POPULARITY_DESC: "order_popular",
    MediaSort.SCORE_DESC: "order_top",
    MediaSort.FAVOURITES_DESC: "order_favorite",
    MediaSort.UPDATED_AT_DESC: "order_updated",
    MediaSort.START_DATE_DESC: "aired_start",
    MediaSort.TITLE_ROMAJI: "title",
    MediaSort.TITLE_ENGLISH: "title",
    MediaSort.ID: "title",
}

_STATUSES = {
    MediaStatus.RELEASING: "Currently Airing",
    MediaStatus.FINISHED: "Finished Airing",
}

#: anidb's genre filter takes numeric ids.
_GENRE_IDS = {
    "Action": 1,
    "Adventure": 3,
    "Comedy": 5,
    "Drama": 2,
    "Ecchi": 13,
    "Fantasy": 4,
    "Hentai": 15,
    "Horror": 21,
    "Mystery": 7,
    "Romance": 14,
    "Sci-Fi": 6,
    "Slice of Life": 9,
    "Sports": 11,
    "Supernatural": 10,
}


class AniDBApi(BaseApiClient):
    """Read-only browse backend served by the same host as the streams."""

    # anidb.app is behind Cloudflare; a real desktop UA passes where the
    # factory's random UA does not always.
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    # ---- fetching --------------------------------------------------------
    def _get(self, url: str) -> Optional[str]:
        try:
            response = self.http_client.get(
                url, headers=self._HEADERS, timeout=TIMEOUT, follow_redirects=True
            )
            response.raise_for_status()
        except Exception as e:  # noqa: BLE001 - network, never fatal
            logger.debug("anidb fetch failed for %s: %s", url, e)
            self.note_failure(self._explain(e))
            return None
        self.clear_failure()
        return response.text

    @staticmethod
    def _explain(error: Exception) -> str:
        """Turn a fetch failure into something worth putting on screen."""
        status = getattr(getattr(error, "response", None), "status_code", None)
        if status == 503:
            # What the site itself serves while its owner is over quota or
            # doing maintenance - it is down for everyone, not just us.
            return (
                "anidb.app is down (HTTP 503 - the site is serving its "
                "'Under Maintenance' page). Nothing to fix on your end; "
                "try another provider or wait for the site to come back."
            )
        if status == 429:
            return (
                "anidb.app is rate limiting us (HTTP 429). Wait a few minutes "
                "or switch provider."
            )
        if status is not None:
            return f"anidb.app returned HTTP {status}."
        return f"Could not reach anidb.app ({type(error).__name__}: {error})."

    def _query(self, params: "MediaSearchParams") -> str:
        """Translate MediaSearchParams into an anidb /browse query string."""
        query: dict = {}
        if params.query:
            query["q"] = params.query

        sort = params.sort
        if isinstance(sort, list):
            sort = sort[0] if sort else None
        if sort is not None and sort in _SORTS:
            query["sort"] = _SORTS[sort]

        status = params.status
        if status is None and params.status_in:
            status = params.status_in[0]
        if status is not None and status in _STATUSES:
            query["status"] = _STATUSES[status]
        elif status is MediaStatus.NOT_YET_RELEASED:
            # anidb's catalogue only distinguishes airing from finished, so
            # "Upcoming" is approximated by the newest entries.
            query["sort"] = "aired_start"

        if params.genre_in:
            ids = [
                _GENRE_IDS[g.value] for g in params.genre_in if g.value in _GENRE_IDS
            ]
            if ids:
                query["genres"] = ids[0]  # anidb filters on one genre at a time

        if params.seasonYear:
            query["year"] = params.seasonYear
        if params.season:
            query["season"] = str(params.season.value).lower()

        if params.page and params.page > 1:
            query["page"] = params.page
        return urlencode(query)

    def _enrich(self, result: MediaSearchResult, page: str) -> MediaSearchResult:
        """Fill in synopsis/genres/status from each show's detail page.

        Cards carry no description or genres, which would leave the preview pane
        bare. Detail pages are fetched concurrently and folded in; any that fail
        simply leave that entry as-is.
        """
        slugs = mapper.slugs_for(page)
        if not slugs or not result.media:
            return result

        pairs = list(zip(result.media, slugs))
        try:
            with ThreadPoolExecutor(max_workers=_ENRICH_WORKERS) as pool:
                pages = list(
                    pool.map(lambda s: self._get(DETAIL_URL.format(s)), slugs)
                )
        except Exception as e:  # noqa: BLE001 - enrichment is optional
            logger.debug("anidb enrichment pass failed: %s", e)
            return result

        enriched = [
            mapper.enrich_from_detail(item, detail) if detail else item
            for (item, _), detail in zip(pairs, pages)
        ]
        return result.model_copy(update={"media": enriched})

    # ---- browse ----------------------------------------------------------
    def search_media(
        self, params: "MediaSearchParams"
    ) -> Optional[MediaSearchResult]:
        """Every browse screen in the app funnels through here."""
        url = f"{BROWSE_URL}?{self._query(params)}"
        page = self._get(url)
        if page is None:
            return None

        result = mapper.to_search_result(page, current_page=params.page or 1)
        if result is None or not result.media:
            return result
        return self._enrich(result, page)

    def transform_raw_search_data(self, raw_data) -> Optional[MediaSearchResult]:
        """Map an already-fetched browse page (used by the dynamic search menu)."""
        if not isinstance(raw_data, str):
            return None
        return mapper.to_search_result(raw_data)

    def fetch_trending_media(
        self, page: int = 1, per_page: int = 28
    ) -> Optional[MediaSearchResult]:
        from ..params import MediaSearchParams

        return self.search_media(
            MediaSearchParams(sort=MediaSort.TRENDING_DESC, page=page)
        )

    def fetch_popular_media(
        self, page: int = 1, per_page: int = 28
    ) -> Optional[MediaSearchResult]:
        from ..params import MediaSearchParams

        return self.search_media(
            MediaSearchParams(sort=MediaSort.POPULARITY_DESC, page=page)
        )

    def fetch_favourite_media(
        self, page: int = 1, per_page: int = 28
    ) -> Optional[MediaSearchResult]:
        from ..params import MediaSearchParams

        return self.search_media(
            MediaSearchParams(sort=MediaSort.FAVOURITES_DESC, page=page)
        )

    def get_related_anime_for(
        self, params: "MediaRelationsParams"
    ) -> Optional[List[MediaItem]]:
        """anidb links a show's other seasons from its detail page."""
        return None

    # ---- account features anidb has no concept of ------------------------
    def is_authenticated(self) -> bool:
        return False

    def authenticate(self, token: str) -> Optional[UserProfile]:
        logger.debug("anidb browsing has no accounts; personal lists stay local.")
        return None

    def get_viewer_profile(self) -> Optional[UserProfile]:
        return None

    def search_media_list(
        self, params: "UserMediaListSearchParams"
    ) -> Optional[MediaSearchResult]:
        # The menus fall back to the on-disk registry when this returns None,
        # which is what makes personal lists work without an account.
        return None

    def update_list_entry(self, params: "UpdateUserMediaListEntryParams") -> bool:
        return False

    def delete_list_entry(self, media_id: int) -> bool:
        return False

    def get_recommendation_for(
        self, params: "MediaRecommendationParams"
    ) -> Optional[List[MediaItem]]:
        return None

    def get_characters_of(
        self, params: "MediaCharactersParams"
    ) -> Optional[CharacterSearchResult]:
        return None

    def get_airing_schedule_for(
        self, params: "MediaAiringScheduleParams"
    ) -> Optional[AiringScheduleResult]:
        return None

    def get_reviews_for(
        self, params: "MediaReviewsParams"
    ) -> Optional[List[MediaReview]]:
        return None

    def get_notifications(self) -> Optional[List[Notification]]:
        return None
