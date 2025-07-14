"""
Tests for the main menu functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from fastanime.cli.interactive.menus.main import main
from fastanime.cli.interactive.state import ControlFlow, State, MediaApiState
from fastanime.libs.api.types import MediaSearchResult, PageInfo as ApiPageInfo


class TestMainMenu:
    """Test cases for the main menu."""

    def test_main_menu_displays_options(self, mock_context, empty_state):
        """Test that the main menu displays all expected options."""
        # Setup selector to return None (exit)
        mock_context.selector.choose.return_value = None
        
        result = main(mock_context, empty_state)
        
        # Should return EXIT when no choice is made
        assert result == ControlFlow.EXIT
        
        # Verify selector was called with expected options
        mock_context.selector.choose.assert_called_once()
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        
        # Check that key options are present
        expected_options = [
            "Trending", "Popular", "Favourites", "Top Scored", 
            "Upcoming", "Recently Updated", "Random", "Search",
            "Watching", "Planned", "Completed", "Paused", "Dropped", "Rewatching",
            "Local Watch History", "Authentication", "Session Management", 
            "Edit Config", "Exit"
        ]
        
        for option in expected_options:
            assert any(option in choice for choice in choices)

    def test_main_menu_trending_selection(self, mock_context, empty_state):
        """Test selecting trending anime from main menu."""
        # Setup selector to return trending choice
        trending_choice = next(choice for choice in self._get_menu_choices(mock_context) 
                             if "Trending" in choice)
        mock_context.selector.choose.return_value = trending_choice
        
        # Mock successful API call
        mock_search_result = MediaSearchResult(
            media=[], 
            page_info=ApiPageInfo(
                total=0,
                current_page=1,
                has_next_page=False,
                per_page=15
            )
        )
        mock_context.media_api.search_media.return_value = mock_search_result
        
        with patch('fastanime.cli.interactive.menus.main.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, mock_search_result)
            
            result = main(mock_context, empty_state)
            
            # Should transition to RESULTS state
            assert isinstance(result, State)
            assert result.menu_name == "RESULTS"
            assert result.media_api.search_results == mock_search_result

    def test_main_menu_search_selection(self, mock_context, empty_state):
        """Test selecting search from main menu."""
        search_choice = next(choice for choice in self._get_menu_choices(mock_context)
                           if "Search" in choice)
        mock_context.selector.choose.return_value = search_choice
        mock_context.selector.ask.return_value = "test query"
        
        # Mock successful API call
        mock_search_result = MediaSearchResult(
            media=[], 
            page_info=ApiPageInfo(
                total=0,
                current_page=1,
                has_next_page=False,
                per_page=15
            )
        )
        
        with patch('fastanime.cli.interactive.menus.main.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, mock_search_result)
            
            result = main(mock_context, empty_state)
            
            # Should transition to RESULTS state
            assert isinstance(result, State)
            assert result.menu_name == "RESULTS"
            assert result.media_api.search_results == mock_search_result

    def test_main_menu_search_empty_query(self, mock_context, empty_state):
        """Test search with empty query returns to menu."""
        search_choice = next(choice for choice in self._get_menu_choices(mock_context) 
                           if "Search" in choice)
        mock_context.selector.choose.return_value = search_choice
        mock_context.selector.ask.return_value = ""  # Empty query
        
        result = main(mock_context, empty_state)
        
        # Should return CONTINUE when search query is empty
        assert result == ControlFlow.CONTINUE

    def test_main_menu_user_list_authenticated(self, mock_context, empty_state):
        """Test accessing user list when authenticated."""
        watching_choice = next(choice for choice in self._get_menu_choices(mock_context) 
                             if "Watching" in choice)
        mock_context.selector.choose.return_value = watching_choice
        
        # Ensure user is authenticated
        mock_context.media_api.is_authenticated.return_value = True
        
        mock_search_result = MediaSearchResult(
            media=[], 
            page_info=ApiPageInfo(
                total=0,
                current_page=1,
                has_next_page=False,
                per_page=15
            )
        )
        
        with patch('fastanime.cli.interactive.menus.main.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, mock_search_result)
            
            result = main(mock_context, empty_state)
            
            # Should transition to RESULTS state
            assert isinstance(result, State)
            assert result.menu_name == "RESULTS"

    def test_main_menu_user_list_not_authenticated(self, mock_context, empty_state):
        """Test accessing user list when not authenticated."""
        watching_choice = next(choice for choice in self._get_menu_choices(mock_context) 
                             if "Watching" in choice)
        mock_context.selector.choose.return_value = watching_choice
        
        # User not authenticated
        mock_context.media_api.is_authenticated.return_value = False
        
        with patch('fastanime.cli.interactive.menus.main.check_authentication_required') as mock_auth:
            mock_auth.return_value = False  # Authentication check fails
            
            result = main(mock_context, empty_state)
            
            # Should return CONTINUE when authentication is required but not provided
            assert result == ControlFlow.CONTINUE

    def test_main_menu_exit_selection(self, mock_context, empty_state):
        """Test selecting exit from main menu."""
        exit_choice = next(choice for choice in self._get_menu_choices(mock_context) 
                         if "Exit" in choice)
        mock_context.selector.choose.return_value = exit_choice
        
        result = main(mock_context, empty_state)
        
        assert result == ControlFlow.EXIT

    def test_main_menu_config_edit_selection(self, mock_context, empty_state):
        """Test selecting config edit from main menu."""
        config_choice = next(choice for choice in self._get_menu_choices(mock_context) 
                           if "Edit Config" in choice)
        mock_context.selector.choose.return_value = config_choice
        
        result = main(mock_context, empty_state)
        
        assert result == ControlFlow.RELOAD_CONFIG

    def test_main_menu_session_management_selection(self, mock_context, empty_state):
        """Test selecting session management from main menu."""
        session_choice = next(choice for choice in self._get_menu_choices(mock_context) 
                            if "Session Management" in choice)
        mock_context.selector.choose.return_value = session_choice
        
        result = main(mock_context, empty_state)
        
        assert isinstance(result, State)
        assert result.menu_name == "SESSION_MANAGEMENT"

    def test_main_menu_auth_selection(self, mock_context, empty_state):
        """Test selecting authentication from main menu."""
        auth_choice = next(choice for choice in self._get_menu_choices(mock_context) 
                         if "Authentication" in choice)
        mock_context.selector.choose.return_value = auth_choice
        
        result = main(mock_context, empty_state)
        
        assert isinstance(result, State)
        assert result.menu_name == "AUTH"

    def test_main_menu_watch_history_selection(self, mock_context, empty_state):
        """Test selecting local watch history from main menu."""
        history_choice = next(choice for choice in self._get_menu_choices(mock_context) 
                            if "Local Watch History" in choice)
        mock_context.selector.choose.return_value = history_choice
        
        result = main(mock_context, empty_state)
        
        assert isinstance(result, State)
        assert result.menu_name == "WATCH_HISTORY"

    def test_main_menu_api_failure(self, mock_context, empty_state):
        """Test handling API failures in main menu."""
        trending_choice = next(choice for choice in self._get_menu_choices(mock_context) 
                             if "Trending" in choice)
        mock_context.selector.choose.return_value = trending_choice
        
        with patch('fastanime.cli.interactive.menus.main.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (False, None)  # API failure
            
            result = main(mock_context, empty_state)
            
            # Should return CONTINUE on API failure
            assert result == ControlFlow.CONTINUE

    def test_main_menu_random_selection(self, mock_context, empty_state):
        """Test selecting random anime from main menu."""
        random_choice = next(choice for choice in self._get_menu_choices(mock_context)
                           if "Random" in choice)
        mock_context.selector.choose.return_value = random_choice
        
        mock_search_result = MediaSearchResult(
            media=[], 
            page_info=ApiPageInfo(
                total=0,
                current_page=1,
                has_next_page=False,
                per_page=15
            )
        )
        
        with patch('fastanime.cli.interactive.menus.main.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, mock_search_result)
            
            result = main(mock_context, empty_state)
            
            # Should transition to RESULTS state
            assert isinstance(result, State)
            assert result.menu_name == "RESULTS"
            assert result.media_api.search_results == mock_search_result

    def test_main_menu_icons_enabled(self, mock_context, empty_state):
        """Test main menu with icons enabled."""
        mock_context.config.general.icons = True
        
        # Just ensure menu doesn't crash with icons enabled
        mock_context.selector.choose.return_value = None
        
        result = main(mock_context, empty_state)
        assert result == ControlFlow.EXIT

    def test_main_menu_icons_disabled(self, mock_context, empty_state):
        """Test main menu with icons disabled."""
        mock_context.config.general.icons = False
        
        # Just ensure menu doesn't crash with icons disabled
        mock_context.selector.choose.return_value = None
        
        result = main(mock_context, empty_state)
        assert result == ControlFlow.EXIT

    def _get_menu_choices(self, mock_context):
        """Helper to get the menu choices from a mock call."""
        # Temporarily call the menu to get choices
        mock_context.selector.choose.return_value = None
        main(mock_context, State(menu_name="TEST"))
        
        # Extract choices from the call
        call_args = mock_context.selector.choose.call_args
        return call_args[1]['choices']


class TestMainMenuHelperFunctions:
    """Test the helper functions in main menu."""

    def test_create_media_list_action_success(self, mock_context):
        """Test creating a media list action that succeeds."""
        from fastanime.cli.interactive.menus.main import _create_media_list_action
        
        action = _create_media_list_action(mock_context, "TRENDING_DESC")
        
        mock_search_result = MediaSearchResult(
            media=[], 
            page_info=ApiPageInfo(
                total=0,
                current_page=1,
                has_next_page=False,
                per_page=15
            )
        )
        
        with patch('fastanime.cli.interactive.menus.main.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, mock_search_result)
            
            menu_name, result, api_params, user_list_params = action()
            
            assert menu_name == "RESULTS"
            assert result == mock_search_result
            assert api_params is not None
            assert user_list_params is None

    def test_create_media_list_action_failure(self, mock_context):
        """Test creating a media list action that fails."""
        from fastanime.cli.interactive.menus.main import _create_media_list_action
        
        action = _create_media_list_action(mock_context, "TRENDING_DESC")
        
        with patch('fastanime.cli.interactive.menus.main.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (False, None)
            
            menu_name, result, api_params, user_list_params = action()
            
            assert menu_name == "CONTINUE"
            assert result is None
            assert api_params is None
            assert user_list_params is None

    def test_create_user_list_action_authenticated(self, mock_context):
        """Test creating a user list action when authenticated."""
        from fastanime.cli.interactive.menus.main import _create_user_list_action
        
        action = _create_user_list_action(mock_context, "CURRENT")
        
        mock_search_result = MediaSearchResult(
            media=[], 
            page_info=ApiPageInfo(
                total=0,
                current_page=1,
                has_next_page=False,
                per_page=15
            )
        )
        
        with patch('fastanime.cli.interactive.menus.main.check_authentication_required') as mock_auth:
            mock_auth.return_value = True
            
            with patch('fastanime.cli.interactive.menus.main.execute_with_feedback') as mock_execute:
                mock_execute.return_value = (True, mock_search_result)
                
                menu_name, result, api_params, user_list_params = action()
                
                assert menu_name == "RESULTS"
                assert result == mock_search_result
                assert api_params is None
                assert user_list_params is not None

    def test_create_user_list_action_not_authenticated(self, mock_context):
        """Test creating a user list action when not authenticated."""
        from fastanime.cli.interactive.menus.main import _create_user_list_action
        
        action = _create_user_list_action(mock_context, "CURRENT")
        
        with patch('fastanime.cli.interactive.menus.main.check_authentication_required') as mock_auth:
            mock_auth.return_value = False
            
            menu_name, result, api_params, user_list_params = action()
            
            assert menu_name == "CONTINUE"
            assert result is None
            assert api_params is None
            assert user_list_params is None

    def test_create_search_media_list_with_query(self, mock_context):
        """Test creating a search media list action with a query."""
        from fastanime.cli.interactive.menus.main import _create_search_media_list
        
        action = _create_search_media_list(mock_context)
        
        mock_context.selector.ask.return_value = "test query"
        mock_search_result = MediaSearchResult(
            media=[], 
            page_info=ApiPageInfo(
                total=0,
                current_page=1,
                has_next_page=False,
                per_page=15
            )
        )
        
        with patch('fastanime.cli.interactive.menus.main.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, mock_search_result)
            
            menu_name, result, api_params, user_list_params = action()
            
            assert menu_name == "RESULTS"
            assert result == mock_search_result
            assert api_params is not None
            assert user_list_params is None

    def test_create_search_media_list_no_query(self, mock_context):
        """Test creating a search media list action without a query."""
        from fastanime.cli.interactive.menus.main import _create_search_media_list
        
        action = _create_search_media_list(mock_context)
        
        mock_context.selector.ask.return_value = ""  # Empty query
        
        menu_name, result, api_params, user_list_params = action()
        
        assert menu_name == "CONTINUE"
        assert result is None
        assert api_params is None
        assert user_list_params is None

    def test_create_random_media_list(self, mock_context):
        """Test creating a random media list action."""
        from fastanime.cli.interactive.menus.main import _create_random_media_list
        
        action = _create_random_media_list(mock_context)
        
        mock_search_result = MediaSearchResult(
            media=[], 
            page_info=ApiPageInfo(
                total=0,
                current_page=1,
                has_next_page=False,
                per_page=15
            )
        )
        
        with patch('fastanime.cli.interactive.menus.main.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, mock_search_result)
            
            menu_name, result, api_params, user_list_params = action()
            
            assert menu_name == "RESULTS"
            assert result == mock_search_result
            assert api_params is not None
            assert user_list_params is None
            # Check that random IDs were used
            assert api_params.id_in is not None
            assert len(api_params.id_in) == 50
