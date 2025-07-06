from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Optional

from .types import MediaSearchResult, UserProfile

if TYPE_CHECKING:
    from httpx import Client

    from ...core.config import AnilistConfig  # Import the specific config part


# --- Parameter Dataclasses (Unchanged) ---


@dataclass(frozen=True)
class ApiSearchParams:
    query: Optional[str] = None
    page: int = 1
    per_page: int = 20
    sort: Optional[str] = None


@dataclass(frozen=True)
class UserListParams:
    status: Literal[
        "CURRENT", "PLANNING", "COMPLETED", "DROPPED", "PAUSED", "REPEATING"
    ]
    page: int = 1
    per_page: int = 20


@dataclass(frozen=True)
class UpdateListEntryParams:
    media_id: int
    status: Optional[
        Literal["CURRENT", "PLANNING", "COMPLETED", "DROPPED", "PAUSED", "REPEATING"]
    ] = None
    progress: Optional[int] = None
    score: Optional[float] = None


# --- Abstract Base Class (Simplified) ---


class BaseApiClient(abc.ABC):
    """
    Abstract Base Class defining a generic contract for media database APIs.
    """

    # The constructor now expects a specific config model, not the whole AppConfig.
    def __init__(self, config: AnilistConfig | Any, client: Client):
        self.config = config
        self.http_client = client

    # --- Authentication & User ---
    @abc.abstractmethod
    def authenticate(self, token: str) -> Optional[UserProfile]:
        pass

    @abc.abstractmethod
    def get_viewer_profile(self) -> Optional[UserProfile]:
        pass

    # --- Media Browsing & Search ---
    @abc.abstractmethod
    def search_media(self, params: ApiSearchParams) -> Optional[MediaSearchResult]:
        """Searches for media based on a query and other filters."""
        pass

    # Redundant fetch methods are REMOVED.

    # --- User List Management ---
    @abc.abstractmethod
    def fetch_user_list(self, params: UserListParams) -> Optional[MediaSearchResult]:
        pass

    @abc.abstractmethod
    def update_list_entry(self, params: UpdateListEntryParams) -> bool:
        pass

    @abc.abstractmethod
    def delete_list_entry(self, media_id: int) -> bool:
        pass
