from __future__ import annotations

import os

import pytest
from fastanime.core.config import AnilistConfig, AppConfig
from fastanime.libs.api.base import ApiSearchParams
from fastanime.libs.api.factory import create_api_client
from fastanime.libs.api.types import MediaItem, MediaSearchResult
from httpx import Client

# Mark the entire module as 'integration'. This test will only run if you explicitly ask for it.
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def live_api_client() -> AniListApi:
    """
    Creates an API client that makes REAL network requests.
    This fixture has 'module' scope so it's created only once for all tests in this file.
    """
    # We create a dummy AppConfig to pass to the factory
    # Note: For authenticated tests, you would load a real token from env vars here.
    config = AppConfig()
    return create_api_client("anilist", config)


def test_search_media_live(live_api_client: AniListApi):
    """
    GIVEN a live connection to the AniList API
    WHEN search_media is called with a common query
    THEN it should return a valid and non-empty MediaSearchResult.
    """
    # ARRANGE
    params = ApiSearchParams(query="Cowboy Bebop", per_page=1)

    # ACT
    result = live_api_client.search_media(params)

    # ASSERT
    assert result is not None
    assert isinstance(result, MediaSearchResult)
    assert len(result.media) > 0

    cowboy_bebop = result.media[0]
    assert isinstance(cowboy_bebop, MediaItem)
    assert cowboy_bebop.id == 1  # Cowboy Bebop's AniList ID
    assert "Cowboy Bebop" in cowboy_bebop.title.english
    assert "Action" in cowboy_bebop.genres


@pytest.mark.skipif(
    not os.getenv("ANILIST_TOKEN"), reason="ANILIST_TOKEN environment variable not set"
)
def test_authenticated_fetch_user_list_live():
    """
    GIVEN a valid ANILIST_TOKEN is set as an environment variable
    WHEN fetching the user's 'CURRENT' list
    THEN it should succeed and return a MediaSearchResult.
    """
    # ARRANGE
    # For authenticated tests, we create a client inside the test
    # so we can configure it with a real token.
    token = os.getenv("ANILIST_TOKEN")
    config = AppConfig()  # Dummy config

    # Create a real client and authenticate it
    from fastanime.libs.api.anilist.api import AniListApi

    real_http_client = Client()
    live_auth_client = AniListApi(config.anilist, real_http_client)
    profile = live_auth_client.authenticate(token)

    assert profile is not None, "Authentication failed with the provided ANILIST_TOKEN"

    # ACT
    from fastanime.libs.api.base import UserListParams

    params = UserListParams(status="CURRENT", per_page=5)
    result = live_auth_client.fetch_user_list(params)

    # ASSERT
    # We can't know the exact content, but we can check the structure.
    assert result is not None
    assert isinstance(result, MediaSearchResult)
    # It's okay if the list is empty, but the call should succeed.
    assert isinstance(result.media, list)
