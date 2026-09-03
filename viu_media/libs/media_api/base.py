import abc
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ...core.config import AnilistConfig
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
    from httpx import Client


class BaseApiClient(abc.ABC):
    """
    Abstract Base Class defining a generic contract for media database APIs.
    """

    #: Why the most recent call came back empty, in words a user can act on.
    #: Backends here answer an outage with ``None`` rather than an exception,
    #: which the menus used to render as a silent bounce back to the main menu
    #: - the app looked frozen when it was merely unable to reach a host. Any
    #: backend that gives up should say so here; the menus read it and show it.
    last_error: Optional[str] = None

    def __init__(self, config: AnilistConfig | Any, client: "Client"):
        self.config = config
        self.http_client = client
        self.last_error = None

    def note_failure(self, message: str) -> None:
        """Record why a call failed so the UI can explain itself."""
        self.last_error = message

    def clear_failure(self) -> None:
        self.last_error = None

    @abc.abstractmethod
    def authenticate(self, token: str) -> Optional[UserProfile]:
        pass

    @abc.abstractmethod
    def is_authenticated(self) -> bool:
        pass

    @abc.abstractmethod
    def get_viewer_profile(self) -> Optional[UserProfile]:
        pass

    @abc.abstractmethod
    def search_media(self, params: MediaSearchParams) -> Optional[MediaSearchResult]:
        """Searches for media based on a query and other filters."""
        pass

    @abc.abstractmethod
    def search_media_list(
        self, params: UserMediaListSearchParams
    ) -> Optional[MediaSearchResult]:
        pass

    @abc.abstractmethod
    def update_list_entry(self, params: UpdateUserMediaListEntryParams) -> bool:
        pass

    @abc.abstractmethod
    def delete_list_entry(self, media_id: int) -> bool:
        pass

    @abc.abstractmethod
    def get_recommendation_for(
        self, params: MediaRecommendationParams
    ) -> Optional[List[MediaItem]]:
        pass

    @abc.abstractmethod
    def get_characters_of(
        self, params: MediaCharactersParams
    ) -> Optional[CharacterSearchResult]:
        pass

    @abc.abstractmethod
    def get_related_anime_for(
        self, params: MediaRelationsParams
    ) -> Optional[List[MediaItem]]:
        pass

    @abc.abstractmethod
    def get_airing_schedule_for(
        self, params: MediaAiringScheduleParams
    ) -> Optional[AiringScheduleResult]:
        pass

    @abc.abstractmethod
    def get_reviews_for(
        self, params: MediaReviewsParams
    ) -> Optional[List[MediaReview]]:
        pass

    @abc.abstractmethod
    def get_notifications(self) -> Optional[List[Notification]]:
        """Fetches the user's unread notifications."""
        pass

    @abc.abstractmethod
    def transform_raw_search_data(self, raw_data: Dict) -> Optional[MediaSearchResult]:
        """
        Transform raw API response data into a MediaSearchResult.

        Args:
            raw_data: Raw response data from the API

        Returns:
            MediaSearchResult object or None if transformation fails
        """
        pass
