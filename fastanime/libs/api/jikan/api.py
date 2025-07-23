from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

from ..base import (
    BaseApiClient,
    MediaSearchParams,
    UpdateUserMediaListEntryParams,
    UserMediaListSearchParams,
)
from ..types import MediaItem, MediaSearchResult, UserProfile
from . import mapper

if TYPE_CHECKING:
    from httpx import Client

    from ....core.config import AppConfig

logger = logging.getLogger(__name__)

JIKAN_ENDPOINT = "https://api.jikan.moe/v4"


class JikanApi(BaseApiClient):
    """
    Jikan API (MyAnimeList) implementation of the BaseApiClient contract.
    Note: Jikan is a read-only API for public data. All authentication and
    list modification methods will be no-ops.
    """

    def _execute_request(
        self, endpoint: str, params: Optional[dict] = None
    ) -> Optional[dict]:
        """Executes a GET request to a Jikan endpoint."""
        try:
            response = self.http_client.get(
                f"{JIKAN_ENDPOINT}{endpoint}", params=params, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Jikan API request failed for endpoint '{endpoint}': {e}")
            return None

    # --- Read-Only Method Implementations ---

    def search_media(self, params: MediaSearchParams) -> Optional[MediaSearchResult]:
        """Searches for anime on MyAnimeList via Jikan."""
        jikan_params = {
            "q": params.query,
            "page": params.page,
            "limit": params.per_page,
        }
        raw_data = self._execute_request("/anime", params=jikan_params)
        return mapper.to_generic_search_result(raw_data) if raw_data else None

    def fetch_trending_media(
        self, page: int, per_page: int
    ) -> Optional[MediaSearchResult]:
        """Jikan doesn't have a 'trending' sort, so we'll use 'bypopularity'."""
        jikan_params = {"order_by": "popularity", "page": page, "limit": per_page}
        raw_data = self._execute_request("/anime", params=jikan_params)
        return mapper.to_generic_search_result(raw_data) if raw_data else None

    def fetch_popular_media(
        self, page: int, per_page: int
    ) -> Optional[MediaSearchResult]:
        """Alias for trending in Jikan's case."""
        return self.fetch_trending_media(page, per_page)

    def fetch_favourite_media(
        self, page: int, per_page: int
    ) -> Optional[MediaSearchResult]:
        """Fetches the most favorited media."""
        jikan_params = {"order_by": "favorites", "page": page, "limit": per_page}
        raw_data = self._execute_request("/anime", params=jikan_params)
        return mapper.to_generic_search_result(raw_data) if raw_data else None

    # --- No-Op Methods (Jikan is Read-Only) ---

    def authenticate(self, token: str) -> Optional[UserProfile]:
        logger.warning("Jikan API does not support authentication.")
        return None

    def get_viewer_profile(self) -> Optional[UserProfile]:
        logger.warning("Jikan API does not support user profiles.")
        return None

    def fetch_user_list(
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
