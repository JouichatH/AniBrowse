from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, List, Optional

from ....core.utils.graphql import execute_graphql_mutation, execute_graphql_query
from ..base import ApiSearchParams, BaseApiClient, UpdateListEntryParams, UserListParams
from ..types import MediaSearchResult, UserProfile
from . import gql, mapper

if TYPE_CHECKING:
    from httpx import Client

    from ....core.config import AnilistConfig

logger = logging.getLogger(__name__)
ANILIST_ENDPOINT = "https://graphql.anilist.co"


class AniListApi(BaseApiClient):
    """AniList API implementation of the BaseApiClient contract."""

    def __init__(self, config: AnilistConfig, client: Client):
        super().__init__(config, client)
        self.token: Optional[str] = None
        self.user_profile: Optional[UserProfile] = None

    def authenticate(self, token: str) -> Optional[UserProfile]:
        self.token = token
        self.http_client.headers["Authorization"] = f"Bearer {token}"
        self.user_profile = self.get_viewer_profile()
        if not self.user_profile:
            self.token = None
            self.http_client.headers.pop("Authorization", None)
        return self.user_profile

    def get_viewer_profile(self) -> Optional[UserProfile]:
        if not self.token:
            return None
        raw_data = execute_graphql_query(
            ANILIST_ENDPOINT, self.http_client, gql.GET_LOGGED_IN_USER, {}
        )
        return mapper.to_generic_user_profile(raw_data) if raw_data else None

    def search_media(self, params: ApiSearchParams) -> Optional[MediaSearchResult]:
        variables = {k: v for k, v in params.__dict__.items() if v is not None}
        variables["perPage"] = params.per_page
        raw_data = execute_graphql_query(
            ANILIST_ENDPOINT, self.http_client, gql.SEARCH_MEDIA, variables
        )
        return mapper.to_generic_search_result(raw_data) if raw_data else None

    def fetch_user_list(self, params: UserListParams) -> Optional[MediaSearchResult]:
        if not self.user_profile:
            logger.error("Cannot fetch user list: user is not authenticated.")
            return None
        variables = {
            "userId": self.user_profile.id,
            "status": params.status,
            "page": params.page,
            "perPage": params.per_page,
        }
        raw_data = execute_graphql_query(
            ANILIST_ENDPOINT, self.http_client, gql.GET_USER_LIST, variables
        )
        return mapper.to_generic_user_list_result(raw_data) if raw_data else None

    def update_list_entry(self, params: UpdateListEntryParams) -> bool:
        if not self.token:
            return False
        score_raw = int(params.score * 10) if params.score is not None else None
        variables = {
            "mediaId": params.media_id,
            "status": params.status,
            "progress": params.progress,
            "scoreRaw": score_raw,
        }
        variables = {k: v for k, v in variables.items() if v is not None}
        response = execute_graphql_mutation(
            ANILIST_ENDPOINT, self.http_client, gql.SAVE_MEDIA_LIST_ENTRY, variables
        )
        return response is not None and "errors" not in response

    def delete_list_entry(self, media_id: int) -> bool:
        if not self.token:
            return False
        entry_data = execute_graphql_query(
            ANILIST_ENDPOINT,
            self.http_client,
            gql.GET_MEDIA_LIST_ITEM,
            {"mediaId": media_id},
        )
        list_id = (
            entry_data.get("data", {}).get("MediaList", {}).get("id")
            if entry_data
            else None
        )
        if not list_id:
            return False
        response = execute_graphql_mutation(
            ANILIST_ENDPOINT,
            self.http_client,
            gql.DELETE_MEDIA_LIST_ENTRY,
            {"id": list_id},
        )
        return (
            response.get("data", {})
            .get("DeleteMediaListEntry", {})
            .get("deleted", False)
            if response
            else False
        )
