"""Keep browsing alive when a metadata backend goes down.

Every browse screen funnels through ``search_media``. When the configured
backend is unreachable that call returns ``None``, every menu bounces
straight back to the main menu, and the app looks frozen rather than
broken - which is exactly what happened when AniList disabled its API
(2026-08) and again when anidb.app went "Under Maintenance" (2026-09).

``FailoverApiClient`` wraps the configured backend and, the first time a
browse comes back empty, tries the remaining backends. The one that answers
is *promoted* for the rest of the session, so every follow-up call (details,
characters, list updates) hits the same backend that produced the items on
screen. That matters because media ids are namespaced per backend - mixing
them per call would hand an anidb id to AniList.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .base import BaseApiClient
from .params import (
    MediaAiringScheduleParams,
    MediaCharactersParams,
    MediaRecommendationParams,
    MediaRelationsParams,
    MediaReviewsParams,
    MediaSearchParams,
    UpdateUserMediaListEntryParams,
    UserMediaListSearchParams,
)
from .types import (
    AiringScheduleResult,
    CharacterSearchResult,
    MediaItem,
    MediaReview,
    MediaSearchResult,
    Notification,
    UserProfile,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class FailoverApiClient(BaseApiClient):
    """Delegates to one live backend, switching when browsing goes dark."""

    def __init__(
        self,
        primary_name: str,
        primary: BaseApiClient,
        standbys: List[str],
        factory: Callable[[str], BaseApiClient],
    ):
        # Deliberately not calling super().__init__: this client owns no
        # config or http client of its own, it only forwards.
        self.active_name = primary_name
        self.active = primary
        self._standbys = list(standbys)
        self._factory = factory
        self._failures: List[str] = []
        self.last_error: Optional[str] = None

    # ---- failover ---------------------------------------------------------
    def _promote(self, name: str, client: BaseApiClient) -> None:
        logger.warning(
            "Metadata backend '%s' returned nothing; switched to '%s' "
            "for the rest of this session.",
            self.active_name,
            name,
        )
        self.active_name = name
        self.active = client

    @staticmethod
    def _reason(client: BaseApiClient, error: Optional[Exception]) -> str:
        """The clearest available explanation for one backend giving up."""
        if error is not None:
            return str(error) or f"{type(error).__name__}"
        return client.last_error or "returned no results"

    def _attempt(
        self, name: str, client: BaseApiClient, call: Callable[[BaseApiClient], Any]
    ) -> tuple[Optional[Any], str]:
        """Run one backend, converting a raised outage into a readable reason."""
        try:
            result = call(client)
        except Exception as e:  # noqa: BLE001 - an outage must not crash browsing
            logger.debug("Backend '%s' failed: %s", name, e)
            return None, self._reason(client, e)
        if result:
            return result, ""
        return None, self._reason(client, None)

    def _try_standbys(
        self, call: Callable[[BaseApiClient], Optional[Any]]
    ) -> Optional[Any]:
        """Run ``call`` against each standby, promoting the first that answers."""
        while self._standbys:
            name = self._standbys.pop(0)
            try:
                client = self._factory(name)
            except Exception as e:  # noqa: BLE001 - a broken backend must not crash browsing
                logger.debug("Could not build fallback backend '%s': %s", name, e)
                self._failures.append(f"{name}: could not be started ({e})")
                continue
            result, reason = self._attempt(name, client, call)
            if result:
                self._promote(name, client)
                return result
            self._failures.append(f"{name}: {reason}")
        return None

    # ---- browsing (the only paths that fail over) -------------------------
    def search_media(self, params: MediaSearchParams) -> Optional[MediaSearchResult]:
        self._failures = []
        result, reason = self._attempt(
            self.active_name, self.active, lambda c: c.search_media(params)
        )
        if result:
            self.last_error = None
            return result

        self._failures.append(f"{self.active_name}: {reason}")
        result = self._try_standbys(lambda c: c.search_media(params))
        if result:
            self.last_error = None
            return result

        # Nothing answered anywhere - say what each backend said, so the
        # screen explains the outage instead of silently going blank.
        self.last_error = "; ".join(self._failures)
        return None

    # ---- everything else follows the active backend -----------------------
    def authenticate(self, token: str) -> Optional[UserProfile]:
        return self.active.authenticate(token)

    def is_authenticated(self) -> bool:
        return self.active.is_authenticated()

    def get_viewer_profile(self) -> Optional[UserProfile]:
        return self.active.get_viewer_profile()

    def search_media_list(
        self, params: UserMediaListSearchParams
    ) -> Optional[MediaSearchResult]:
        return self.active.search_media_list(params)

    def update_list_entry(self, params: UpdateUserMediaListEntryParams) -> bool:
        return self.active.update_list_entry(params)

    def delete_list_entry(self, media_id: int) -> bool:
        return self.active.delete_list_entry(media_id)

    def get_recommendation_for(
        self, params: MediaRecommendationParams
    ) -> Optional[List[MediaItem]]:
        return self.active.get_recommendation_for(params)

    def get_characters_of(
        self, params: MediaCharactersParams
    ) -> Optional[CharacterSearchResult]:
        return self.active.get_characters_of(params)

    def get_related_anime_for(
        self, params: MediaRelationsParams
    ) -> Optional[List[MediaItem]]:
        return self.active.get_related_anime_for(params)

    def get_airing_schedule_for(
        self, params: MediaAiringScheduleParams
    ) -> Optional[AiringScheduleResult]:
        return self.active.get_airing_schedule_for(params)

    def get_reviews_for(
        self, params: MediaReviewsParams
    ) -> Optional[List[MediaReview]]:
        return self.active.get_reviews_for(params)

    def get_notifications(self) -> Optional[List[Notification]]:
        return self.active.get_notifications()

    def transform_raw_search_data(self, raw_data: Dict) -> Optional[MediaSearchResult]:
        return self.active.transform_raw_search_data(raw_data)

    # ``config``/``http_client`` are read by a few call sites and by tests.
    @property
    def config(self) -> Any:  # type: ignore[override]
        return self.active.config

    @property
    def http_client(self) -> Any:  # type: ignore[override]
        return self.active.http_client
