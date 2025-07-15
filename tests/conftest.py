"""
Pytest configuration and shared fixtures for FastAnime tests.
Provides common mocks and test utilities following DRY principles.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
from typing import Dict, Any, Optional

from fastanime.core.config import AppConfig, GeneralConfig, AnilistConfig
from fastanime.cli.interactive.session import Context
from fastanime.cli.interactive.state import State, ControlFlow, ProviderState, MediaApiState
from fastanime.libs.api.types import UserProfile, MediaSearchResult, MediaItem
from fastanime.libs.api.base import BaseApiClient
from fastanime.libs.providers.anime.base import BaseAnimeProvider
from fastanime.libs.selectors.base import BaseSelector
from fastanime.libs.players.base import BasePlayer


@pytest.fixture
def mock_config():
    """Create a mock AppConfig with default settings."""
    config = Mock(spec=AppConfig)
    config.general = Mock(spec=GeneralConfig)
    config.general.icons = True
    config.general.provider = "test_provider"
    config.general.api_client = "anilist"
    config.anilist = Mock(spec=AnilistConfig)
    return config


@pytest.fixture
def mock_user_profile():
    """Create a mock user profile for authenticated tests."""
    return UserProfile(
        id=12345,
        name="TestUser",
        avatar="https://example.com/avatar.jpg"
    )


@pytest.fixture
def mock_media_item():
    """Create a mock media item for testing."""
    return MediaItem(
        id=1,
        title="Test Anime",
        description="A test anime description",
        cover_image="https://example.com/cover.jpg",
        banner_image="https://example.com/banner.jpg",
        status="RELEASING",
        episodes=12,
        duration=24,
        genres=["Action", "Adventure"],
        mean_score=85,
        popularity=1000,
        start_date="2024-01-01",
        end_date=None
    )


@pytest.fixture
def mock_media_search_result(mock_media_item):
    """Create a mock media search result."""
    return MediaSearchResult(
        media=[mock_media_item],
        page_info={
            "total": 1,
            "current_page": 1,
            "last_page": 1,
            "has_next_page": False,
            "per_page": 20
        }
    )


@pytest.fixture
def mock_api_client(mock_user_profile):
    """Create a mock API client."""
    client = Mock(spec=BaseApiClient)
    client.user_profile = mock_user_profile
    client.authenticate.return_value = mock_user_profile
    client.get_viewer_profile.return_value = mock_user_profile
    client.search_media.return_value = None
    return client


@pytest.fixture
def mock_unauthenticated_api_client():
    """Create a mock API client without authentication."""
    client = Mock(spec=BaseApiClient)
    client.user_profile = None
    client.authenticate.return_value = None
    client.get_viewer_profile.return_value = None
    client.search_media.return_value = None
    return client


@pytest.fixture
def mock_provider():
    """Create a mock anime provider."""
    provider = Mock(spec=BaseAnimeProvider)
    provider.search.return_value = None
    provider.get_anime.return_value = None
    provider.get_servers.return_value = []
    return provider


@pytest.fixture
def mock_selector():
    """Create a mock selector for user input."""
    selector = Mock(spec=BaseSelector)
    selector.choose.return_value = None
    selector.input.return_value = ""
    selector.confirm.return_value = False
    return selector


@pytest.fixture
def mock_player():
    """Create a mock player."""
    player = Mock(spec=BasePlayer)
    player.play.return_value = None
    return player


@pytest.fixture
def mock_context(mock_config, mock_provider, mock_selector, mock_player, mock_api_client):
    """Create a mock context with all dependencies."""
    return Context(
        config=mock_config,
        provider=mock_provider,
        selector=mock_selector,
        player=mock_player,
        media_api=mock_api_client
    )


@pytest.fixture
def mock_unauthenticated_context(mock_config, mock_provider, mock_selector, mock_player, mock_unauthenticated_api_client):
    """Create a mock context without authentication."""
    return Context(
        config=mock_config,
        provider=mock_provider,
        selector=mock_selector,
        player=mock_player,
        media_api=mock_unauthenticated_api_client
    )


@pytest.fixture
def basic_state():
    """Create a basic state for testing."""
    return State(menu_name="TEST")


@pytest.fixture
def state_with_media_data(mock_media_search_result, mock_media_item):
    """Create a state with media data."""
    return State(
        menu_name="TEST",
        media_api=MediaApiState(
            search_results=mock_media_search_result,
            anime=mock_media_item
        )
    )


@pytest.fixture
def mock_feedback_manager():
    """Create a mock feedback manager."""
    feedback = Mock()
    feedback.info = Mock()
    feedback.error = Mock()
    feedback.warning = Mock()
    feedback.success = Mock()
    feedback.confirm.return_value = False
    feedback.pause_for_user = Mock()
    return feedback


@pytest.fixture
def mock_console():
    """Create a mock Rich console."""
    console = Mock()
    console.clear = Mock()
    console.print = Mock()
    return console


class MenuTestHelper:
    """Helper class for common menu testing patterns."""
    
    @staticmethod
    def assert_control_flow(result: Any, expected: ControlFlow):
        """Assert that the result is the expected ControlFlow."""
        assert isinstance(result, ControlFlow)
        assert result == expected
    
    @staticmethod
    def assert_state_transition(result: Any, expected_menu: str):
        """Assert that the result is a State with the expected menu name."""
        assert isinstance(result, State)
        assert result.menu_name == expected_menu
    
    @staticmethod
    def setup_selector_choice(mock_selector, choice: Optional[str]):
        """Helper to set up selector choice return value."""
        mock_selector.choose.return_value = choice
    
    @staticmethod
    def setup_selector_confirm(mock_selector, confirm: bool):
        """Helper to set up selector confirm return value."""
        mock_selector.confirm.return_value = confirm
    
    @staticmethod
    def setup_feedback_confirm(mock_feedback, confirm: bool):
        """Helper to set up feedback confirm return value."""
        mock_feedback.confirm.return_value = confirm


@pytest.fixture
def menu_helper():
    """Provide the MenuTestHelper class."""
    return MenuTestHelper


# Patches for external dependencies
@pytest.fixture
def mock_create_feedback_manager(mock_feedback_manager):
    """Mock the create_feedback_manager function."""
    with patch('fastanime.cli.utils.feedback.create_feedback_manager', return_value=mock_feedback_manager):
        yield mock_feedback_manager


@pytest.fixture
def mock_rich_console(mock_console):
    """Mock the Rich Console class."""
    with patch('rich.console.Console', return_value=mock_console):
        yield mock_console


@pytest.fixture
def mock_click_edit():
    """Mock the click.edit function."""
    with patch('click.edit') as mock_edit:
        yield mock_edit


@pytest.fixture
def mock_webbrowser_open():
    """Mock the webbrowser.open function."""
    with patch('webbrowser.open') as mock_open:
        yield mock_open


@pytest.fixture
def mock_auth_manager():
    """Mock the AuthManager class."""
    with patch('fastanime.cli.auth.manager.AuthManager') as mock_auth:
        auth_instance = Mock()
        auth_instance.load_user_profile.return_value = None
        auth_instance.save_user_profile.return_value = True
        auth_instance.clear_user_profile.return_value = True
        mock_auth.return_value = auth_instance
        yield auth_instance


# Common test data
TEST_MENU_OPTIONS = {
    'trending': '🔥 Trending',
    'popular': '✨ Popular', 
    'favourites': '💖 Favourites',
    'top_scored': '💯 Top Scored',
    'upcoming': '🎬 Upcoming',
    'recently_updated': '🔔 Recently Updated',
    'random': '🎲 Random',
    'search': '🔎 Search',
    'watching': '📺 Watching',
    'planned': '📑 Planned',
    'completed': '✅ Completed',
    'paused': '⏸️ Paused',
    'dropped': '🚮 Dropped',
    'rewatching': '🔁 Rewatching',
    'watch_history': '📖 Local Watch History',
    'auth': '🔐 Authentication',
    'session_management': '🔧 Session Management',
    'edit_config': '📝 Edit Config',
    'exit': '❌ Exit'
}

TEST_AUTH_OPTIONS = {
    'login': '🔐 Login to AniList',
    'logout': '🔓 Logout',
    'profile': '👤 View Profile Details',
    'how_to_token': '❓ How to Get Token',
    'back': '↩️ Back to Main Menu'
}
