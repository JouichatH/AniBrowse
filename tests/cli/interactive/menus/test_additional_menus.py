"""
Tests for remaining interactive menus.
Tests servers, provider search, and player controls menus.
"""

from unittest.mock import Mock, patch

import pytest
from fastanime.cli.interactive.state import (
    ControlFlow,
    MediaApiState,
    ProviderState,
    State,
)
from fastanime.libs.providers.anime.types import Server

from .base_test import BaseMenuTest, MediaMenuTestMixin


class TestServersMenu(BaseMenuTest, MediaMenuTestMixin):
    """Test cases for the servers menu."""

    @pytest.fixture
    def mock_servers(self):
        """Create mock server list."""
        return [
            Server(name="Server 1", url="https://server1.com/stream"),
            Server(name="Server 2", url="https://server2.com/stream"),
            Server(name="Server 3", url="https://server3.com/stream"),
        ]

    @pytest.fixture
    def servers_state(self, mock_provider_anime, mock_media_item, mock_servers):
        """Create state with servers data."""
        return State(
            menu_name="SERVERS",
            provider=ProviderState(
                anime=mock_provider_anime, selected_episode="5", servers=mock_servers
            ),
            media_api=MediaApiState(anime=mock_media_item),
        )

    def test_servers_menu_no_servers_goes_back(self, mock_context, basic_state):
        """Test that no servers returns BACK."""
        from fastanime.cli.interactive.menus.servers import servers

        state_no_servers = State(
            menu_name="SERVERS", provider=ProviderState(servers=[])
        )

        result = servers(mock_context, state_no_servers)

        self.assert_back_behavior(result)
        self.assert_console_cleared()

    def test_servers_menu_server_selection(self, mock_context, servers_state):
        """Test server selection and stream playback."""
        from fastanime.cli.interactive.menus.servers import servers

        self.setup_selector_choice(mock_context, "Server 1")

        # Mock successful stream extraction
        mock_context.provider.get_stream_url.return_value = "https://stream.url"
        mock_context.player.play.return_value = Mock()

        result = servers(mock_context, servers_state)

        # Should return to episodes or continue based on playback result
        assert isinstance(result, (State, ControlFlow))
        self.assert_console_cleared()

    def test_servers_menu_auto_select_best_server(self, mock_context, servers_state):
        """Test auto-selecting best quality server."""
        from fastanime.cli.interactive.menus.servers import servers

        mock_context.config.stream.auto_select_server = True
        mock_context.provider.get_stream_url.return_value = "https://stream.url"
        mock_context.player.play.return_value = Mock()

        result = servers(mock_context, servers_state)

        # Should auto-select and play
        assert isinstance(result, (State, ControlFlow))
        self.assert_console_cleared()


class TestProviderSearchMenu(BaseMenuTest, MediaMenuTestMixin):
    """Test cases for the provider search menu."""

    def test_provider_search_no_choice_goes_back(self, mock_context, basic_state):
        """Test that no choice returns BACK."""
        from fastanime.cli.interactive.menus.provider_search import provider_search

        self.setup_selector_choice(mock_context, None)

        result = provider_search(mock_context, basic_state)

        self.assert_back_behavior(result)
        self.assert_console_cleared()

    def test_provider_search_success(self, mock_context, state_with_media_data):
        """Test successful provider search."""
        from fastanime.cli.interactive.menus.provider_search import provider_search
        from fastanime.libs.providers.anime.types import Anime, SearchResults

        # Mock search results
        mock_anime = Mock(spec=Anime)
        mock_search_results = Mock(spec=SearchResults)
        mock_search_results.results = [mock_anime]

        mock_context.provider.search.return_value = mock_search_results
        self.setup_selector_choice(mock_context, "Test Anime Result")

        result = provider_search(mock_context, state_with_media_data)

        self.assert_menu_transition(result, "EPISODES")
        self.assert_console_cleared()

    def test_provider_search_no_results(self, mock_context, state_with_media_data):
        """Test provider search with no results."""
        from fastanime.cli.interactive.menus.provider_search import provider_search

        mock_context.provider.search.return_value = None

        result = provider_search(mock_context, state_with_media_data)

        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        self.assert_feedback_error_called("No results found")


class TestPlayerControlsMenu(BaseMenuTest):
    """Test cases for the player controls menu."""

    def test_player_controls_no_active_player_goes_back(
        self, mock_context, basic_state
    ):
        """Test that no active player returns BACK."""
        from fastanime.cli.interactive.menus.player_controls import player_controls

        mock_context.player.is_active = False

        result = player_controls(mock_context, basic_state)

        self.assert_back_behavior(result)
        self.assert_console_cleared()

    def test_player_controls_pause_resume(self, mock_context, basic_state):
        """Test pause/resume controls."""
        from fastanime.cli.interactive.menus.player_controls import player_controls

        mock_context.player.is_active = True
        mock_context.player.is_paused = False
        self.setup_selector_choice(mock_context, "⏸️ Pause")

        result = player_controls(mock_context, basic_state)

        self.assert_continue_behavior(result)
        mock_context.player.pause.assert_called_once()

    def test_player_controls_seek(self, mock_context, basic_state):
        """Test seek controls."""
        from fastanime.cli.interactive.menus.player_controls import player_controls

        mock_context.player.is_active = True
        self.setup_selector_choice(mock_context, "⏩ Seek Forward")

        result = player_controls(mock_context, basic_state)

        self.assert_continue_behavior(result)
        mock_context.player.seek.assert_called_once()

    def test_player_controls_volume(self, mock_context, basic_state):
        """Test volume controls."""
        from fastanime.cli.interactive.menus.player_controls import player_controls

        mock_context.player.is_active = True
        self.setup_selector_choice(mock_context, "🔊 Volume Up")

        result = player_controls(mock_context, basic_state)

        self.assert_continue_behavior(result)
        mock_context.player.volume_up.assert_called_once()

    def test_player_controls_stop(self, mock_context, basic_state):
        """Test stop playback."""
        from fastanime.cli.interactive.menus.player_controls import player_controls

        mock_context.player.is_active = True
        self.setup_selector_choice(mock_context, "⏹️ Stop")
        self.setup_feedback_confirm(True)  # Confirm stop

        result = player_controls(mock_context, basic_state)

        self.assert_back_behavior(result)
        mock_context.player.stop.assert_called_once()


# Integration tests for menu flow
class TestMenuIntegration(BaseMenuTest, MediaMenuTestMixin):
    """Integration tests for menu navigation flow."""

    def test_full_navigation_flow(self, mock_context, mock_media_search_result):
        """Test complete navigation from main to watching anime."""
        from fastanime.cli.interactive.menus.main import main
        from fastanime.cli.interactive.menus.media_actions import media_actions
        from fastanime.cli.interactive.menus.provider_search import provider_search
        from fastanime.cli.interactive.menus.results import results

        # Start from main menu
        main_state = State(menu_name="MAIN")

        # Mock main menu choice - trending
        self.setup_selector_choice(mock_context, "🔥 Trending")
        self.setup_media_list_success(mock_context, mock_media_search_result)

        # Should go to results
        result = main(mock_context, main_state)
        self.assert_menu_transition(result, "RESULTS")

        # Now test results menu
        results_state = result
        anime_title = f"{mock_media_search_result.media[0].title} ({mock_media_search_result.media[0].status})"

        with patch(
            "fastanime.cli.interactive.menus.results._format_anime_choice",
            return_value=anime_title,
        ):
            self.setup_selector_choice(mock_context, anime_title)

            result = results(mock_context, results_state)
            self.assert_menu_transition(result, "MEDIA_ACTIONS")

        # Test media actions
        actions_state = result
        self.setup_selector_choice(mock_context, "🔍 Search Providers")

        result = media_actions(mock_context, actions_state)
        self.assert_menu_transition(result, "PROVIDER_SEARCH")

    def test_error_recovery_flow(self, mock_context, basic_state):
        """Test error recovery in menu navigation."""
        from fastanime.cli.interactive.menus.main import main

        # Mock API failure
        self.setup_selector_choice(mock_context, "🔥 Trending")
        self.setup_media_list_failure(mock_context)

        result = main(mock_context, basic_state)

        # Should continue (show error and stay in menu)
        self.assert_continue_behavior(result)
        self.assert_feedback_error_called("Failed to fetch data")

    def test_authentication_flow_integration(
        self, mock_unauthenticated_context, basic_state
    ):
        """Test authentication-dependent features."""
        from fastanime.cli.interactive.menus.auth import auth
        from fastanime.cli.interactive.menus.main import main

        # Try to access user list without auth
        self.setup_selector_choice(mock_unauthenticated_context, "📺 Watching")

        # Should either redirect to auth or show error
        result = main(mock_unauthenticated_context, basic_state)

        # Result depends on implementation - could be CONTINUE with error or AUTH redirect
        assert isinstance(result, (State, ControlFlow))

    @pytest.mark.parametrize(
        "menu_choice,expected_transition",
        [
            ("🔧 Session Management", "SESSION_MANAGEMENT"),
            ("🔐 Authentication", "AUTH"),
            ("📖 Local Watch History", "WATCH_HISTORY"),
            ("❌ Exit", ControlFlow.EXIT),
            ("📝 Edit Config", ControlFlow.CONFIG_EDIT),
        ],
    )
    def test_main_menu_navigation_paths(
        self, mock_context, basic_state, menu_choice, expected_transition
    ):
        """Test various navigation paths from main menu."""
        from fastanime.cli.interactive.menus.main import main

        self.setup_selector_choice(mock_context, menu_choice)

        result = main(mock_context, basic_state)

        if isinstance(expected_transition, str):
            self.assert_menu_transition(result, expected_transition)
        else:
            assert result == expected_transition
