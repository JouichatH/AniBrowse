import logging
from typing import Optional

from httpx import Client

from ....core.config import AnilistConfig
from ....core.utils.graphql import (
    execute_graphql,
)
from ..base import ApiSearchParams, BaseApiClient, UpdateListEntryParams, UserListParams
from ..types import MediaSearchResult, UserProfile
from . import gql, mapper

logger = logging.getLogger(__name__)
ANILIST_ENDPOINT = "https://graphql.anilist.co"


status_map = {
    "watching": "CURRENT",
    "planning": "PLANNING",
    "completed": "COMPLETED",
    "dropped": "DROPPED",
    "paused": "PAUSED",
    "repeating": "REPEATING",
}

# TODO: Just remove and have consistent variable naming between the two
search_params_map = {
    # Custom Name: AniList Variable Name
    "query": "query",
    "page": "page",
    "per_page": "per_page",
    "sort": "sort",
    "id_in": "id_in",
    "genre_in": "genre_in",
    "genre_not_in": "genre_not_in",
    "tag_in": "tag_in",
    "tag_not_in": "tag_not_in",
    "status_in": "status_in",
    "status": "status",
    "status_not_in": "status_not_in",
    "popularity_greater": "popularity_greater",
    "popularity_lesser": "popularity_lesser",
    "averageScore_greater": "averageScore_greater",
    "averageScore_lesser": "averageScore_lesser",
    "seasonYear": "seasonYear",
    "season": "season",
    "startDate_greater": "startDate_greater",
    "startDate_lesser": "startDate_lesser",
    "startDate": "startDate",
    "endDate_greater": "endDate_greater",
    "endDate_lesser": "endDate_lesser",
    "format_in": "format_in",
    "type": "type",
    "on_list": "on_list",
}


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

    def is_authenticated(self) -> bool:
        return True if self.user_profile else False

    def get_viewer_profile(self) -> Optional[UserProfile]:
        if not self.token:
            return None
        response = execute_graphql(
            ANILIST_ENDPOINT, self.http_client, gql.GET_LOGGED_IN_USER, {}
        )
        return mapper.to_generic_user_profile(response.json())

    def search_media(self, params: ApiSearchParams) -> Optional[MediaSearchResult]:
        variables = {
            search_params_map[k]: v for k, v in params.__dict__.items() if v is not None
        }
        variables["per_page"] = params.per_page or self.config.per_page

        # ignore hentai by default
        variables["genre_not_in"] = params.genre_not_in or ["Hentai"]

        # anime by default
        variables["type"] = params.type or "ANIME"
        response = execute_graphql(
            ANILIST_ENDPOINT, self.http_client, gql.SEARCH_MEDIA, variables
        )
        return mapper.to_generic_search_result(response.json())

    def search_media_list(self, params: UserListParams) -> Optional[MediaSearchResult]:
        if not self.user_profile:
            logger.error("Cannot fetch user list: user is not authenticated.")
            return None

        # TODO: use consistent variable naming btw graphql and params
        # so variables can be dynamically filled
        variables = {
            "sort": params.sort or self.config.media_list_sort_by,
            "userId": self.user_profile.id,
            "status": status_map[params.status] if params.status else None,
            "page": params.page,
            "perPage": params.per_page or self.config.per_page,
            "type": params.type or "ANIME",
        }
        response = execute_graphql(
            ANILIST_ENDPOINT, self.http_client, gql.GET_USER_MEDIA_LIST, variables
        )
        return mapper.to_generic_user_list_result(response.json()) if response else None

    def update_list_entry(self, params: UpdateListEntryParams) -> bool:
        if not self.token:
            return False
        score_raw = int(params.score * 10) if params.score is not None else None
        variables = {
            "mediaId": params.media_id,
            "status": status_map[params.status] if params.status else None,
            "progress": int(float(params.progress)) if params.progress else None,
            "scoreRaw": score_raw,
        }
        variables = {k: v for k, v in variables.items() if v is not None}
        response = execute_graphql(
            ANILIST_ENDPOINT, self.http_client, gql.SAVE_MEDIA_LIST_ENTRY, variables
        )
        return response.json() is not None and "errors" not in response.json()

    def delete_list_entry(self, media_id: int) -> bool:
        if not self.token:
            return False
        response = execute_graphql(
            ANILIST_ENDPOINT,
            self.http_client,
            gql.GET_MEDIA_LIST_ITEM,
            {"mediaId": media_id},
        )
        entry_data = response.json()

        list_id = (
            entry_data.get("data", {}).get("MediaList", {}).get("id")
            if entry_data
            else None
        )
        if not list_id:
            return False
        response = execute_graphql(
            ANILIST_ENDPOINT,
            self.http_client,
            gql.DELETE_MEDIA_LIST_ENTRY,
            {"id": list_id},
        )
        return (
            response.json()
            .get("data", {})
            .get("DeleteMediaListEntry", {})
            .get("deleted", False)
            if response
            else False
        )


if __name__ == "__main__":
    from httpx import Client

    from ....core.config import AnilistConfig
    from ....core.constants import APP_ASCII_ART
    from ..params import ApiSearchParams

    anilist = AniListApi(AnilistConfig(), Client())
    print(APP_ASCII_ART)

    # search
    query = input("What anime would you like to search for: ")
    search_results = anilist.search_media(ApiSearchParams(query=query))
    if not search_results:
        print("Nothing was finding matching: ", query)
        exit()
    for result in search_results.media:
        print(
            f"Title: {result.title.english or result.title.romaji} Episodes: {result.episodes}"
        )
