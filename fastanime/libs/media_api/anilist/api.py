import logging
from enum import Enum
from typing import Dict, List, Optional

from httpx import Client

from ....core.config import AnilistConfig
from ....core.utils.graphql import (
    execute_graphql,
)
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
from ..types import MediaItem, MediaSearchResult, UserMediaListStatus, UserProfile
from . import gql, mapper

logger = logging.getLogger(__name__)
ANILIST_ENDPOINT = "https://graphql.anilist.co"


user_list_status_map = {
    UserMediaListStatus.WATCHING: "CURRENT",
    UserMediaListStatus.PLANNING: "PLANNING",
    UserMediaListStatus.COMPLETED: "COMPLETED",
    UserMediaListStatus.DROPPED: "DROPPED",
    UserMediaListStatus.PAUSED: "PAUSED",
    UserMediaListStatus.REPEATING: "REPEATING",
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

    def search_media(self, params: MediaSearchParams) -> Optional[MediaSearchResult]:
        variables = {
            search_params_map[k]: v
            for k, v in params.__dict__.items()
            if v is not None and not isinstance(v, Enum)
        }

        # handle case where value is an enum
        variables.update(
            {
                search_params_map[k]: v.value
                for k, v in params.__dict__.items()
                if v is not None and isinstance(v, Enum)
            }
        )

        # handle case where is a list of enums
        variables.update(
            {
                search_params_map[k]: list(map(lambda item: item.value, v))
                for k, v in params.__dict__.items()
                if v is not None and isinstance(v, list) and isinstance(v[0], Enum)
            }
        )

        variables["per_page"] = params.per_page or self.config.per_page

        # ignore hentai by default
        variables["genre_not_in"] = (
            list(map(lambda item: item.value, params.genre_not_in))
            if params.genre_not_in
            else ["Hentai"]
        )

        # anime by default
        variables["type"] = params.type.value if params.type else "ANIME"
        response = execute_graphql(
            ANILIST_ENDPOINT, self.http_client, gql.SEARCH_MEDIA, variables
        )
        return mapper.to_generic_search_result(response.json())

    def search_media_list(
        self, params: UserMediaListSearchParams
    ) -> Optional[MediaSearchResult]:
        if not self.user_profile:
            logger.error("Cannot fetch user list: user is not authenticated.")
            return None

        # TODO: use consistent variable naming btw graphql and params
        # so variables can be dynamically filled
        variables = {
            "sort": params.sort.value
            if params.sort
            else self.config.media_list_sort_by.value,
            "userId": self.user_profile.id,
            "status": user_list_status_map[params.status] if params.status else None,
            "page": params.page,
            "perPage": params.per_page or self.config.per_page,
            "type": params.type.value if params.type else "ANIME",
        }
        response = execute_graphql(
            ANILIST_ENDPOINT, self.http_client, gql.SEARCH_USER_MEDIA_LIST, variables
        )
        return mapper.to_generic_user_list_result(response.json()) if response else None

    def update_list_entry(self, params: UpdateUserMediaListEntryParams) -> bool:
        if not self.token:
            return False
        score_raw = int(params.score * 10) if params.score is not None else None
        variables = {
            "mediaId": params.media_id,
            "status": user_list_status_map[params.status] if params.status else None,
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

    def get_recommendation_for(self, params: MediaRecommendationParams) -> Optional[List[MediaItem]]:
        variables = {
            "id": params.id, 
            "page": params.page,
            "per_page": params.per_page or self.config.per_page
        }
        response = execute_graphql(
            ANILIST_ENDPOINT, self.http_client, gql.GET_MEDIA_RECOMMENDATIONS, variables
        )
        return mapper.to_generic_recommendations(response.json()) if response else None

    def get_characters_of(self, params: MediaCharactersParams) -> Optional[Dict]:
        variables = {"id": params.id, "type": "ANIME"}
        response = execute_graphql(
            ANILIST_ENDPOINT, self.http_client, gql.GET_MEDIA_CHARACTERS, variables
        )
        return response.json() if response else None

    def get_related_anime_for(self, params: MediaRelationsParams) -> Optional[List[MediaItem]]:
        variables = {"id": params.id}
        response = execute_graphql(
            ANILIST_ENDPOINT, self.http_client, gql.GET_MEDIA_RELATIONS, variables
        )
        return mapper.to_generic_relations(response.json()) if response else None

    def get_airing_schedule_for(self, params: MediaAiringScheduleParams) -> Optional[Dict]:
        variables = {"id": params.id, "type": "ANIME"}
        response = execute_graphql(
            ANILIST_ENDPOINT, self.http_client, gql.GET_AIRING_SCHEDULE, variables
        )
        return response.json() if response else None


def test_media_api(api_client: "AniListApi"):
    """
    Test all abstract methods of the media API with user feedback.
    
    This function provides an interactive test suite that validates all the core
    functionality of the media API, similar to test_anime_provider for anime providers.
    
    Tests performed:
    1. Authentication status and user profile retrieval
    2. Media search functionality
    3. Anime recommendations fetching
    4. Related anime retrieval
    5. Character information fetching
    6. Airing schedule information
    7. User media list operations (if authenticated)
    8. List entry management (add/remove from user list)
    
    Args:
        api_client: An instance of AniListApi to test
        
    Usage:
        Run this module directly: python -m fastanime.libs.media_api.anilist.api
        Or import and call: test_media_api(AniListApi(config, client))
    """
    from httpx import Client
    
    from ....core.config import AnilistConfig
    from ....core.constants import APP_ASCII_ART
    from ..params import (
        MediaAiringScheduleParams,
        MediaCharactersParams,
        MediaRecommendationParams,
        MediaRelationsParams,
        MediaSearchParams,
        UpdateUserMediaListEntryParams,
        UserMediaListSearchParams,
    )
    from ..types import UserMediaListStatus

    print(APP_ASCII_ART)
    print("=== Media API Test Suite ===\n")

    # Test 1: Authentication
    print("1. Testing Authentication...")
    print(f"Authenticated: {api_client.is_authenticated()}")
    if api_client.is_authenticated():
        profile = api_client.get_viewer_profile()
        if profile:
            print(f"   User: {profile.name} (ID: {profile.id})")
        else:
            print("   Failed to get user profile")
    else:
        print("   Not authenticated - some features will be limited")
    print()

    # Test 2: Media Search
    print("2. Testing Media Search...")
    query = input("What anime would you like to search for: ")
    search_results = api_client.search_media(MediaSearchParams(query=query, per_page=5))
    
    if not search_results or not search_results.media:
        print("   No search results found")
        return
    
    print(f"   Found {len(search_results.media)} results:")
    for i, result in enumerate(search_results.media):
        title = result.title.english or result.title.romaji
        print(f"   {i + 1}: {title} ({result.episodes or '?'} episodes)")
    
    # Select an anime for further testing
    try:
        choice = int(input(f"\nSelect anime for detailed testing (1-{len(search_results.media)}): ")) - 1
        selected_anime = search_results.media[choice]
    except (ValueError, IndexError):
        print("Invalid selection")
        return
    
    print(f"\nSelected: {selected_anime.title.english or selected_anime.title.romaji}")
    print()

    # Test 3: Get Recommendations
    print("3. Testing Recommendations...")
    try:
        recommendations = api_client.get_recommendation_for(
            MediaRecommendationParams(id=selected_anime.id, page=1, per_page=3)
        )
        if recommendations:
            print(f"   Found {len(recommendations)} recommendations:")
            for rec in recommendations[:3]:  # Show first 3
                title = rec.title.english or rec.title.romaji
                print(f"     - {title}")
        else:
            print("   No recommendations found")
    except Exception as e:
        print(f"   Error: {e}")
    print()

    # Test 4: Get Related Anime
    print("4. Testing Related Anime...")
    try:
        relations = api_client.get_related_anime_for(
            MediaRelationsParams(id=selected_anime.id)
        )
        if relations:
            print(f"   Found {len(relations)} related anime:")
            for rel in relations[:3]:  # Show first 3
                title = rel.title.english or rel.title.romaji
                print(f"     - {title}")
        else:
            print("   No related anime found")
    except Exception as e:
        print(f"   Error: {e}")
    print()

    # Test 5: Get Characters
    print("5. Testing Character Information...")
    try:
        characters = api_client.get_characters_of(
            MediaCharactersParams(id=selected_anime.id)
        )
        if characters and characters.get("data"):
            char_data = characters["data"]["Page"]["media"][0]["characters"]["nodes"]
            if char_data:
                print(f"   Found {len(char_data)} characters:")
                for char in char_data[:3]:  # Show first 3
                    name = char["name"]["full"] or char["name"]["first"]
                    print(f"     - {name}")
            else:
                print("   No character data found")
        else:
            print("   No characters found")
    except Exception as e:
        print(f"   Error: {e}")
    print()

    # Test 6: Get Airing Schedule
    print("6. Testing Airing Schedule...")
    try:
        schedule = api_client.get_airing_schedule_for(
            MediaAiringScheduleParams(id=selected_anime.id)
        )
        if schedule and schedule.get("data"):
            schedule_data = schedule["data"]["Page"]["media"][0]["airingSchedule"]["nodes"]
            if schedule_data:
                print(f"   Found {len(schedule_data)} upcoming episodes:")
                for ep in schedule_data[:3]:  # Show first 3
                    print(f"     - Episode {ep['episode']}")
            else:
                print("   No upcoming episodes")
        else:
            print("   No airing schedule found")
    except Exception as e:
        print(f"   Error: {e}")
    print()

    # Test 7: User Media List (if authenticated)
    if api_client.is_authenticated():
        print("7. Testing User Media List...")
        try:
            user_list = api_client.search_media_list(
                UserMediaListSearchParams(
                    status=UserMediaListStatus.WATCHING,
                    page=1,
                    per_page=3
                )
            )
            if user_list and user_list.media:
                print(f"   Found {len(user_list.media)} watching anime:")
                for anime in user_list.media:
                    title = anime.title.english or anime.title.romaji
                    progress = anime.user_status.progress if anime.user_status else 0
                    print(f"     - {title} (Progress: {progress}/{anime.episodes or '?'})")
            else:
                print("   No anime in watching list")
        except Exception as e:
            print(f"   Error: {e}")
        print()

        # Test 8: Update List Entry
        print("8. Testing List Entry Management...")
        update_test = input("Would you like to test adding the selected anime to your list? (y/n): ")
        if update_test.lower() == 'y':
            try:
                success = api_client.update_list_entry(
                    UpdateUserMediaListEntryParams(
                        media_id=selected_anime.id,
                        status=UserMediaListStatus.PLANNING
                    )
                )
                if success:
                    print("   ✓ Successfully added to planning list")
                    
                    # Test delete
                    delete_test = input("   Would you like to remove it from your list? (y/n): ")
                    if delete_test.lower() == 'y':
                        delete_success = api_client.delete_list_entry(selected_anime.id)
                        if delete_success:
                            print("   ✓ Successfully removed from list")
                        else:
                            print("   ✗ Failed to remove from list")
                else:
                    print("   ✗ Failed to add to list")
            except Exception as e:
                print(f"   Error: {e}")
        print()
    else:
        print("7-8. Skipping user list tests (not authenticated)\n")

    print("=== Test Suite Complete ===")
    print("All basic API methods have been tested!")


if __name__ == "__main__":
    from httpx import Client

    from ....core.config import AnilistConfig

    anilist = AniListApi(AnilistConfig(), Client())
    test_media_api(anilist)
