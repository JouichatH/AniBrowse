"""
Shared test fixtures and utilities for menu testing.
"""

from unittest.mock import Mock, MagicMock
from pathlib import Path
import pytest
from typing import Iterator, List, Optional

from fastanime.core.config.model import AppConfig, GeneralConfig, StreamConfig, AnilistConfig
from fastanime.cli.interactive.session import Context
from fastanime.cli.interactive.state import State, ProviderState, MediaApiState, ControlFlow
from fastanime.libs.api.types import MediaItem, MediaSearchResult, PageInfo, UserProfile
from fastanime.libs.api.params import ApiSearchParams, UserListParams
from fastanime.libs.providers.anime.types import Anime, SearchResults, Server
from fastanime.libs.players.types import PlayerResult


@pytest.fixture
def mock_config():
    """Create a mock configuration object."""
    return AppConfig(
        general=GeneralConfig(
            icons=True,
            provider="allanime",
            selector="fzf",
            api_client="anilist",
            preview="text",
            auto_select_anime_result=True,
            cache_requests=True,
            normalize_titles=True,
            discord=False,
            recent=50
        ),
        stream=StreamConfig(
            player="mpv",
            quality="1080",
            translation_type="sub",
            server="TOP",
            auto_next=False,
            continue_from_watch_history=True,
            preferred_watch_history="local"
        ),
        anilist=AnilistConfig(
            per_page=15,
            sort_by="SEARCH_MATCH",
            preferred_language="english"
        )
    )


@pytest.fixture
def mock_provider():
    """Create a mock anime provider."""
    provider = Mock()
    provider.search_anime.return_value = SearchResults(
        anime=[
            Anime(
                name="Test Anime 1",
                url="https://example.com/anime1",
                id="anime1",
                poster="https://example.com/poster1.jpg"
            )
        ]
    )
    return provider


@pytest.fixture
def mock_selector():
    """Create a mock selector."""
    selector = Mock()
    selector.choose.return_value = "Test Choice"
    selector.ask.return_value = "Test Input"
    return selector


@pytest.fixture
def mock_player():
    """Create a mock player."""
    player = Mock()
    player.play.return_value = PlayerResult(success=True, exit_code=0)
    return player


@pytest.fixture
def mock_media_api():
    """Create a mock media API client."""
    api = Mock()
    
    # Mock user profile
    api.user_profile = UserProfile(
        id=12345,
        name="TestUser",
        avatar="https://example.com/avatar.jpg"
    )
    
    # Mock search results
    api.search_media.return_value = MediaSearchResult(
        media=[
            MediaItem(
                id=1,
                title={"english": "Test Anime", "romaji": "Test Anime"},
                status="FINISHED",
                episodes=12,
                description="A test anime",
                cover_image="https://example.com/cover.jpg",
                banner_image="https://example.com/banner.jpg",
                genres=["Action", "Adventure"],
                studios=[{"name": "Test Studio"}]
            )
        ],
        page_info=PageInfo(
            total=1,
            per_page=15,
            current_page=1,
            has_next_page=False
        )
    )
    
    # Mock user list
    api.fetch_user_list.return_value = api.search_media.return_value
    
    # Mock authentication methods
    api.is_authenticated.return_value = True
    api.authenticate.return_value = True
    
    return api


@pytest.fixture
def mock_context(mock_config, mock_provider, mock_selector, mock_player, mock_media_api):
    """Create a mock context object."""
    return Context(
        config=mock_config,
        provider=mock_provider,
        selector=mock_selector,
        player=mock_player,
        media_api=mock_media_api
    )


@pytest.fixture
def sample_media_item():
    """Create a sample MediaItem for testing."""
    return MediaItem(
        id=1,
        title={"english": "Test Anime", "romaji": "Test Anime"},
        status="FINISHED",
        episodes=12,
        description="A test anime",
        cover_image="https://example.com/cover.jpg",
        banner_image="https://example.com/banner.jpg",
        genres=["Action", "Adventure"],
        studios=[{"name": "Test Studio"}]
    )


@pytest.fixture
def sample_provider_anime():
    """Create a sample provider Anime for testing."""
    return Anime(
        name="Test Anime",
        url="https://example.com/anime",
        id="test-anime",
        poster="https://example.com/poster.jpg"
    )


@pytest.fixture
def sample_search_results(sample_media_item):
    """Create sample search results."""
    return MediaSearchResult(
        media=[sample_media_item],
        page_info=PageInfo(
            total=1,
            per_page=15,
            current_page=1,
            has_next_page=False
        )
    )


@pytest.fixture
def empty_state():
    """Create an empty state."""
    return State(menu_name="TEST")


@pytest.fixture
def state_with_media_api(sample_search_results, sample_media_item):
    """Create a state with media API data."""
    return State(
        menu_name="TEST",
        media_api=MediaApiState(
            search_results=sample_search_results,
            anime=sample_media_item
        )
    )


@pytest.fixture
def state_with_provider(sample_provider_anime):
    """Create a state with provider data."""
    return State(
        menu_name="TEST",
        provider=ProviderState(
            anime=sample_provider_anime,
            episode_number="1"
        )
    )


@pytest.fixture
def full_state(sample_search_results, sample_media_item, sample_provider_anime):
    """Create a state with both media API and provider data."""
    return State(
        menu_name="TEST",
        media_api=MediaApiState(
            search_results=sample_search_results,
            anime=sample_media_item
        ),
        provider=ProviderState(
            anime=sample_provider_anime,
            episode_number="1"
        )
    )


# Test utilities

def assert_state_transition(result, expected_menu_name: str):
    """Assert that a menu function returned a proper state transition."""
    assert isinstance(result, State)
    assert result.menu_name == expected_menu_name


def assert_control_flow(result, expected_flow: ControlFlow):
    """Assert that a menu function returned the expected control flow."""
    assert isinstance(result, ControlFlow)
    assert result == expected_flow


def setup_selector_choices(mock_selector, choices: List[str]):
    """Setup mock selector to return specific choices in sequence."""
    mock_selector.choose.side_effect = choices


def setup_selector_inputs(mock_selector, inputs: List[str]):
    """Setup mock selector to return specific inputs in sequence."""
    mock_selector.ask.side_effect = inputs


# Mock feedback manager
@pytest.fixture
def mock_feedback():
    """Create a mock feedback manager."""
    feedback = Mock()
    feedback.success.return_value = None
    feedback.error.return_value = None
    feedback.info.return_value = None
    feedback.confirm.return_value = True
    feedback.pause_for_user.return_value = None
    return feedback
