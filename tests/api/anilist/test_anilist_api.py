from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastanime.libs.api.anilist.api import AniListApi
from fastanime.libs.api.base import ApiSearchParams, UserListParams
from fastanime.libs.api.types import MediaItem, MediaSearchResult, UserProfile
from httpx import Response

if TYPE_CHECKING:
    from fastanime.core.config import AnilistConfig
    from httpx import Client
    from pytest_httpx import HTTPXMock


# --- Fixtures ---


@pytest.fixture
def mock_anilist_config() -> AnilistConfig:
    """Provides a default AnilistConfig instance for tests."""
    from fastanime.core.config import AnilistConfig

    return AnilistConfig()


@pytest.fixture
def mock_data_path() -> Path:
    """Provides the path to the mock_data directory."""
    return Path(__file__).parent / "mock_data"


@pytest.fixture
def anilist_client(
    mock_anilist_config: AnilistConfig, httpx_mock: HTTPXMock
) -> AniListApi:
    """
    Provides an instance of AniListApi with a mocked HTTP client.
    Note: We pass the httpx_mock fixture which is the mocked client.
    """
    return AniListApi(config=mock_anilist_config, client=httpx_mock)


# --- Test Cases ---


def test_search_media_success(
    anilist_client: AniListApi, httpx_mock: HTTPXMock, mock_data_path: Path
):
    """
    GIVEN a search query for 'one piece'
    WHEN search_media is called
    THEN it should return a MediaSearchResult with one correctly mapped MediaItem.
    """
    # ARRANGE: Load mock response and configure the mock HTTP client.
    mock_response_json = json.loads(
        (mock_data_path / "search_one_piece.json").read_text()
    )
    httpx_mock.add_response(url="https://graphql.anilist.co", json=mock_response_json)

    params = ApiSearchParams(query="one piece")

    # ACT
    result = anilist_client.search_media(params)

    # ASSERT
    assert result is not None
    assert isinstance(result, MediaSearchResult)
    assert len(result.media) == 1

    one_piece = result.media[0]
    assert isinstance(one_piece, MediaItem)
    assert one_piece.id == 21
    assert one_piece.title.english == "ONE PIECE"
    assert one_piece.status == "RELEASING"
    assert "Action" in one_piece.genres
    assert one_piece.average_score == 8.7  # Mapper should convert 87 -> 8.7


def test_fetch_user_list_success(
    anilist_client: AniListApi, httpx_mock: HTTPXMock, mock_data_path: Path
):
    """
    GIVEN an authenticated client
    WHEN fetch_user_list is called for the 'CURRENT' list
    THEN it should return a MediaSearchResult with a correctly mapped MediaItem
         that includes user-specific progress.
    """
    # ARRANGE
    mock_response_json = json.loads(
        (mock_data_path / "user_list_watching.json").read_text()
    )
    httpx_mock.add_response(url="https://graphql.anilist.co", json=mock_response_json)

    # Simulate being logged in
    anilist_client.user_profile = UserProfile(id=12345, name="testuser")

    params = UserListParams(status="CURRENT")

    # ACT
    result = anilist_client.fetch_user_list(params)

    # ASSERT
    assert result is not None
    assert isinstance(result, MediaSearchResult)
    assert len(result.media) == 1

    attack_on_titan = result.media[0]
    assert isinstance(attack_on_titan, MediaItem)
    assert attack_on_titan.id == 16498
    assert attack_on_titan.title.english == "Attack on Titan"

    # Assert that user-specific data was mapped correctly
    assert attack_on_titan.user_list_status is not None
    assert attack_on_titan.user_list_status.status == "CURRENT"
    assert attack_on_titan.user_list_status.progress == 10
    assert attack_on_titan.user_list_status.score == 9.0


def test_update_list_entry_sends_correct_mutation(
    anilist_client: AniListApi, httpx_mock: HTTPXMock
):
    """
    GIVEN an authenticated client
    WHEN update_list_entry is called
    THEN it should send a POST request with the correct GraphQL mutation and variables.
    """
    # ARRANGE
    httpx_mock.add_response(
        url="https://graphql.anilist.co",
        json={"data": {"SaveMediaListEntry": {"id": 54321}}},
    )
    anilist_client.token = "fake-token"  # Simulate authentication

    params = UpdateListEntryParams(media_id=16498, progress=11, status="CURRENT")

    # ACT
    success = anilist_client.update_list_entry(params)

    # ASSERT
    assert success is True

    # Verify the request content
    request = httpx_mock.get_request()
    assert request is not None
    assert request.method == "POST"

    request_body = json.loads(request.content)
    assert "SaveMediaListEntry" in request_body["query"]
    assert request_body["variables"]["mediaId"] == 16498
    assert request_body["variables"]["progress"] == 11
    assert request_body["variables"]["status"] == "CURRENT"
    assert (
        "scoreRaw" not in request_body["variables"]
    )  # Ensure None values are excluded


def test_api_calls_fail_gracefully_on_http_error(
    anilist_client: AniListApi, httpx_mock: HTTPXMock
):
    """
    GIVEN the AniList API returns a 500 server error
    WHEN any API method is called
    THEN it should return None or False and log an error without crashing.
    """
    # ARRANGE
    httpx_mock.add_response(url="https://graphql.anilist.co", status_code=500)

    # ACT & ASSERT
    with pytest.logs("fastanime.libs.api.anilist.api", level="ERROR") as caplog:
        search_result = anilist_client.search_media(ApiSearchParams(query="test"))
        assert search_result is None
        assert "AniList API request failed" in caplog.text

        update_result = anilist_client.update_list_entry(
            UpdateListEntryParams(media_id=1)
        )
        assert update_result is False  # Mutations should return bool
