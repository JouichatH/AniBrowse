import abc
from typing import Any, Optional

from httpx import Client

from ...core.config import AnilistConfig
from .params import ApiSearchParams, UpdateListEntryParams, UserListParams
from .types import MediaSearchResult, UserProfile


class BaseApiClient(abc.ABC):
    """
    Abstract Base Class defining a generic contract for media database APIs.
    """

    def __init__(self, config: AnilistConfig | Any, client: Client):
        self.config = config
        self.http_client = client

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
    def search_media(self, params: ApiSearchParams) -> Optional[MediaSearchResult]:
        """Searches for media based on a query and other filters."""
        pass

    @abc.abstractmethod
    def search_media_list(self, params: UserListParams) -> Optional[MediaSearchResult]:
        pass

    @abc.abstractmethod
    def update_list_entry(self, params: UpdateListEntryParams) -> bool:
        pass

    @abc.abstractmethod
    def delete_list_entry(self, media_id: int) -> bool:
        pass
