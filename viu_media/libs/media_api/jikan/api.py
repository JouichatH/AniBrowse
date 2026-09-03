import logging
import random
import time
from typing import TYPE_CHECKING, List, Optional

from ..base import BaseApiClient
from ..params import (
    MediaAiringScheduleParams,
    MediaCharactersParams,
    MediaRecommendationParams,
    MediaRelationsParams,
    MediaSearchParams,
    UpdateUserMediaListEntryParams,
    UserMediaListSearchParams,
)
from ..types import (
    AiringScheduleResult,
    CharacterSearchResult,
    MediaImage,
    MediaItem,
    MediaReview,
    MediaSearchResult,
    MediaSort,
    MediaStatus,
    MediaTitle,
    Notification,
    UserProfile,
)
from . import mapper

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

JIKAN_ENDPOINT = "https://api.jikan.moe/v4"

# Sorts the menus use that map onto a /top/anime filter. "" = /top/anime's own
# default ordering (by score/rank), which is what SCORE_DESC wants.
_TOP_FILTERS = {
    MediaSort.TRENDING_DESC: "airing",
    MediaSort.POPULARITY_DESC: "bypopularity",
    MediaSort.FAVOURITES_DESC: "favorite",
    MediaSort.SCORE_DESC: "",
}

# Everything else goes to /anime with an explicit ordering.
_ORDER_BY = {
    MediaSort.UPDATED_AT_DESC: ("start_date", "desc"),
    MediaSort.START_DATE_DESC: ("start_date", "desc"),
    MediaSort.EPISODES_DESC: ("episodes", "desc"),
    MediaSort.TITLE_ROMAJI: ("title", "asc"),
    MediaSort.ID: ("mal_id", "asc"),
}


class JikanApi(BaseApiClient):
    """
    Jikan API (MyAnimeList) implementation of the BaseApiClient contract.
    Note: Jikan is a read-only API for public data. All authentication and
    list modification methods will be no-ops.
    """

    def _execute_request(
        self, endpoint: str, params: Optional[dict] = None
    ) -> Optional[dict]:
        """GET a Jikan endpoint, honouring its rate limit.

        Jikan allows ~3 requests/second and answers 429 once you exceed that.
        The app fires several calls per screen (results plus preview workers),
        so a burst is routine and must be waited out rather than surfaced as a
        failure.
        """
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        delay = 1.0
        for attempt in range(3):
            try:
                response = self.http_client.get(
                    f"{JIKAN_ENDPOINT}{endpoint}", params=clean, timeout=15
                )
                if response.status_code == 429 and attempt < 2:
                    logger.debug("Jikan rate-limited %s; retrying in %ss", endpoint, delay)
                    time.sleep(delay)
                    delay *= 2
                    continue
                response.raise_for_status()
                return response.json()
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Jikan API request failed for '{endpoint}': {e}")
                    return None
                time.sleep(delay)
                delay *= 2
        return None

    # --- Read-Only Method Implementations ---

    def search_media(self, params: MediaSearchParams) -> Optional[MediaSearchResult]:
        """Every browse screen funnels through here, so translate the sort too.

        The menus express "Trending"/"Popular"/"Upcoming" as a MediaSort (plus an
        optional status) on an otherwise empty MediaSearchParams. MAL has no
        trending metric, but /top/anime's filters cover the same intents, so a
        sort is routed to the closest endpoint instead of being ignored - which
        is what made every category return one identical list.
        """
        endpoint, extra = self._route(params)
        jikan_params = {
            "q": params.query,
            "page": params.page,
            "limit": params.per_page or self.config.per_page,
            "sfw": "true",
            **extra,
        }
        raw_data = self._execute_request(endpoint, params=jikan_params)
        return mapper.to_generic_search_result(raw_data) if raw_data else None

    def _route(self, params: MediaSearchParams) -> "tuple[str, dict]":
        """(endpoint, extra query params) for a search request."""
        sort = params.sort
        if isinstance(sort, list):
            sort = sort[0] if sort else None

        # A text query always means a plain search; MAL's /top endpoints ignore q.
        if params.query:
            return "/anime", {}

        status = params.status
        if status is MediaStatus.NOT_YET_RELEASED:
            return "/top/anime", {"filter": "upcoming"}

        if sort is not None:
            filter_ = _TOP_FILTERS.get(sort)
            if filter_ is not None:
                # filter_ == "" means /top/anime's default order (by score/rank).
                return "/top/anime", ({"filter": filter_} if filter_ else {})
            order_by, direction = _ORDER_BY.get(sort, ("members", "desc"))
            return "/anime", {"order_by": order_by, "sort": direction}

        # "Random" asks for 50 arbitrary ids, which MAL cannot express. A random
        # page of popular anime keeps the menu useful; ids would cost one
        # request each and blow the rate limit.
        if params.id_in:
            pages = max(1, 300)
            return "/anime", {
                "order_by": "members",
                "sort": "desc",
                "page": random.randint(1, pages),
            }

        return "/anime", {"order_by": "members", "sort": "desc"}

    def fetch_trending_media(
        self, page: int = 1, per_page: int = 25
    ) -> Optional[MediaSearchResult]:
        """MAL has no trending metric; currently-airing top anime is the analogue."""
        raw = self._execute_request(
            "/top/anime", params={"filter": "airing", "page": page, "limit": per_page}
        )
        return mapper.to_generic_search_result(raw) if raw else None

    def fetch_popular_media(
        self, page: int = 1, per_page: int = 25
    ) -> Optional[MediaSearchResult]:
        raw = self._execute_request(
            "/top/anime",
            params={"filter": "bypopularity", "page": page, "limit": per_page},
        )
        return mapper.to_generic_search_result(raw) if raw else None

    def fetch_favourite_media(
        self, page: int = 1, per_page: int = 25
    ) -> Optional[MediaSearchResult]:
        raw = self._execute_request(
            "/top/anime", params={"filter": "favorite", "page": page, "limit": per_page}
        )
        return mapper.to_generic_search_result(raw) if raw else None

    def transform_raw_search_data(self, raw_data) -> Optional[MediaSearchResult]:
        """Map an already-fetched Jikan payload (used by the dynamic search menu)."""
        return mapper.to_generic_search_result(raw_data) if raw_data else None

    def get_reviews_for(self, params) -> Optional[List[MediaReview]]:
        """MAL reviews are long-form prose without the fields the UI renders."""
        logger.debug("Jikan reviews are not mapped; skipping.")
        return None

    # --- No-Op Methods (Jikan is Read-Only) ---

    def is_authenticated(self) -> bool:
        """Jikan is a public API that doesn't require authentication."""
        return False

    def authenticate(self, token: str) -> Optional[UserProfile]:
        logger.warning("Jikan API does not support authentication.")
        return None

    def get_viewer_profile(self) -> Optional[UserProfile]:
        logger.warning("Jikan API does not support user profiles.")
        return None

    def search_media_list(
        self, params: UserMediaListSearchParams
    ) -> Optional[MediaSearchResult]:
        logger.warning("Jikan API does not support fetching user lists.")
        return None

    def update_list_entry(self, params: UpdateUserMediaListEntryParams) -> bool:
        logger.warning("Jikan API does not support updating list entries.")
        return False

    def delete_list_entry(self, media_id: int) -> bool:
        logger.warning("Jikan API does not support deleting list entries.")
        return False

    def get_recommendation_for(
        self, params: MediaRecommendationParams
    ) -> Optional[List[MediaItem]]:
        """Fetches anime recommendations for a given media ID."""
        try:
            endpoint = f"/anime/{params.id}/recommendations"
            raw_data = self._execute_request(endpoint)
            if not raw_data or "data" not in raw_data:
                return None

            recommendations = []
            for item in raw_data["data"]:
                # Jikan recommendation structure has an 'entry' field with anime data
                entry = item.get("entry", {})
                if entry:
                    media_item = mapper._to_generic_media_item(entry)
                    recommendations.append(media_item)

            return recommendations
        except Exception as e:
            logger.error(f"Failed to fetch recommendations for media {params.id}: {e}")
            return None

    def get_characters_of(
        self, params: MediaCharactersParams
    ) -> Optional[CharacterSearchResult]:
        """Fetches characters for a given anime."""
        logger.warning(
            "Jikan API does not support fetching character data in the standardized format."
        )
        return None

    def get_related_anime_for(
        self, params: MediaRelationsParams
    ) -> Optional[List[MediaItem]]:
        """Fetches related anime for a given media ID."""
        try:
            endpoint = f"/anime/{params.id}/relations"
            raw_data = self._execute_request(endpoint)
            if not raw_data or "data" not in raw_data:
                return None

            related_anime = []
            for relation in raw_data["data"]:
                entries = relation.get("entry", [])
                for entry in entries:
                    if entry.get("type") == "anime":
                        # Create a minimal MediaItem from the relation data
                        media_item = MediaItem(
                            id=entry["mal_id"],
                            id_mal=entry["mal_id"],
                            title=MediaTitle(
                                english=entry["name"], romaji=entry["name"], native=None
                            ),
                            cover_image=MediaImage(large=""),
                            description=None,
                            genres=[],
                            studios=[],
                            streaming_episodes={},
                            user_status=None,
                        )
                        related_anime.append(media_item)

            return related_anime
        except Exception as e:
            logger.error(f"Failed to fetch related anime for media {params.id}: {e}")
            return None

    def get_notifications(self) -> Optional[List[Notification]]:
        """Jikan is a public API and does not support user notifications."""
        logger.warning("Jikan API does not support fetching user notifications.")
        return None

    def get_airing_schedule_for(
        self, params: MediaAiringScheduleParams
    ) -> Optional[AiringScheduleResult]:
        """Jikan doesn't provide a direct airing schedule endpoint per anime."""
        logger.warning(
            "Jikan API does not support fetching airing schedules for individual anime."
        )
        return None
