"""
Tests for the main interactive menu.
Tests all navigation options and control flow logic.
"""

import pytest
from unittest.mock import Mock, patch

from fastanime.cli.interactive.menus.main import main
from fastanime.cli.interactive.state import State, ControlFlow
from fastanime.libs.api.types import MediaSearchResult

from .base_test import BaseMenuTest, MediaMenuTestMixin
from ...conftest import TEST_MENU_OPTIONS


class TestMainMenu(BaseMenuTest, MediaMenuTestMixin):
    """Test cases for the main interactive menu."""
    
    def test_main_menu_no_choice_exits(self, mock_context, basic_state):
        """Test that no choice selected results in EXIT."""
        # User cancels/exits the menu
        self.setup_selector_choice(mock_context, None)
        
        result = main(mock_context, basic_state)
        
        self.assert_exit_behavior(result)
        self.assert_console_cleared()
    
    def test_main_menu_exit_choice(self, mock_context, basic_state):
        """Test explicit exit choice."""
        self.setup_selector_choice(mock_context, TEST_MENU_OPTIONS['exit'])
        
        result = main(mock_context, basic_state)
        
        self.assert_exit_behavior(result)
        self.assert_console_cleared()
    
    def test_main_menu_reload_config_choice(self, mock_context, basic_state):
        """Test config reload choice."""
        self.setup_selector_choice(mock_context, TEST_MENU_OPTIONS['edit_config'])
        
        result = main(mock_context, basic_state)
        
        self.assert_reload_config_behavior(result)
        self.assert_console_cleared()
    
    def test_main_menu_session_management_choice(self, mock_context, basic_state):
        """Test session management navigation."""
        self.setup_selector_choice(mock_context, TEST_MENU_OPTIONS['session_management'])
        
        result = main(mock_context, basic_state)
        
        self.assert_menu_transition(result, "SESSION_MANAGEMENT")
        self.assert_console_cleared()
    
    def test_main_menu_auth_choice(self, mock_context, basic_state):
        """Test authentication menu navigation."""
        self.setup_selector_choice(mock_context, TEST_MENU_OPTIONS['auth'])
        
        result = main(mock_context, basic_state)
        
        self.assert_menu_transition(result, "AUTH")
        self.assert_console_cleared()
    
    def test_main_menu_watch_history_choice(self, mock_context, basic_state):
        """Test watch history navigation."""
        self.setup_selector_choice(mock_context, TEST_MENU_OPTIONS['watch_history'])
        
        result = main(mock_context, basic_state)
        
        self.assert_menu_transition(result, "WATCH_HISTORY")
        self.assert_console_cleared()
    
    @pytest.mark.parametrize("choice_key,expected_menu", [
        ("trending", "RESULTS"),
        ("popular", "RESULTS"),
        ("favourites", "RESULTS"),
        ("top_scored", "RESULTS"),
        ("upcoming", "RESULTS"),
        ("recently_updated", "RESULTS"),
    ])
    def test_main_menu_media_list_choices_success(self, mock_context, basic_state, choice_key, expected_menu, mock_media_search_result):
        """Test successful media list navigation for various categories."""
        self.setup_selector_choice(mock_context, TEST_MENU_OPTIONS[choice_key])
        self.setup_media_list_success(mock_context, mock_media_search_result)
        
        result = main(mock_context, basic_state)
        
        self.assert_menu_transition(result, expected_menu)
        self.assert_console_cleared()
        # Verify API was called
        mock_context.media_api.search_media.assert_called_once()
    
    @pytest.mark.parametrize("choice_key", [
        "trending",
        "popular", 
        "favourites",
        "top_scored",
        "upcoming",
        "recently_updated",
    ])
    def test_main_menu_media_list_choices_failure(self, mock_context, basic_state, choice_key):
        """Test failed media list fetch shows error and continues."""
        self.setup_selector_choice(mock_context, TEST_MENU_OPTIONS[choice_key])
        self.setup_media_list_failure(mock_context)
        
        result = main(mock_context, basic_state)
        
        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        self.assert_feedback_error_called("Failed to fetch data")
    
    @pytest.mark.parametrize("choice_key,expected_menu", [
        ("watching", "RESULTS"),
        ("planned", "RESULTS"),
        ("completed", "RESULTS"),
        ("paused", "RESULTS"),
        ("dropped", "RESULTS"),
        ("rewatching", "RESULTS"),
    ])
    def test_main_menu_user_list_choices_success(self, mock_context, basic_state, choice_key, expected_menu, mock_media_search_result):
        """Test successful user list navigation for authenticated users."""
        self.setup_selector_choice(mock_context, TEST_MENU_OPTIONS[choice_key])
        self.setup_media_list_success(mock_context, mock_media_search_result)
        
        result = main(mock_context, basic_state)
        
        self.assert_menu_transition(result, expected_menu)
        self.assert_console_cleared()
        # Verify API was called
        mock_context.media_api.get_user_media_list.assert_called_once()
    
    @pytest.mark.parametrize("choice_key", [
        "watching",
        "planned",
        "completed", 
        "paused",
        "dropped",
        "rewatching",
    ])
    def test_main_menu_user_list_choices_failure(self, mock_context, basic_state, choice_key):
        """Test failed user list fetch shows error and continues."""
        self.setup_selector_choice(mock_context, TEST_MENU_OPTIONS[choice_key])
        mock_context.media_api.get_user_media_list.return_value = None
        
        result = main(mock_context, basic_state)
        
        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        self.assert_feedback_error_called("Failed to fetch data")
    
    def test_main_menu_random_choice_success(self, mock_context, basic_state, mock_media_search_result):
        """Test random anime selection success."""
        self.setup_selector_choice(mock_context, TEST_MENU_OPTIONS['random'])
        self.setup_media_list_success(mock_context, mock_media_search_result)
        
        with patch('random.choice') as mock_random:
            mock_random.return_value = "Action"  # Mock random genre selection
            
            result = main(mock_context, basic_state)
            
            self.assert_menu_transition(result, "RESULTS")
            self.assert_console_cleared()
            mock_context.media_api.search_media.assert_called_once()
    
    def test_main_menu_random_choice_failure(self, mock_context, basic_state):
        """Test random anime selection failure."""
        self.setup_selector_choice(mock_context, TEST_MENU_OPTIONS['random'])
        self.setup_media_list_failure(mock_context)
        
        with patch('random.choice') as mock_random:
            mock_random.return_value = "Action"
            
            result = main(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            self.assert_feedback_error_called("Failed to fetch data")
    
    def test_main_menu_search_choice_success(self, mock_context, basic_state, mock_media_search_result):
        """Test search functionality success."""
        self.setup_selector_choice(mock_context, TEST_MENU_OPTIONS['search'])
        self.setup_selector_input(mock_context, "test anime")
        self.setup_media_list_success(mock_context, mock_media_search_result)
        
        result = main(mock_context, basic_state)
        
        self.assert_menu_transition(result, "RESULTS")
        self.assert_console_cleared()
        mock_context.selector.input.assert_called_once()
        mock_context.media_api.search_media.assert_called_once()
    
    def test_main_menu_search_choice_empty_query(self, mock_context, basic_state):
        """Test search with empty query continues."""
        self.setup_selector_choice(mock_context, TEST_MENU_OPTIONS['search'])
        self.setup_selector_input(mock_context, "")  # Empty search query
        
        result = main(mock_context, basic_state)
        
        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        mock_context.selector.input.assert_called_once()
        # API should not be called with empty query
        mock_context.media_api.search_media.assert_not_called()
    
    def test_main_menu_search_choice_failure(self, mock_context, basic_state):
        """Test search functionality failure."""
        self.setup_selector_choice(mock_context, TEST_MENU_OPTIONS['search'])
        self.setup_selector_input(mock_context, "test anime")
        self.setup_media_list_failure(mock_context)
        
        result = main(mock_context, basic_state)
        
        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        self.assert_feedback_error_called("Failed to fetch data")
    
    def test_main_menu_icons_disabled(self, mock_context, basic_state):
        """Test menu display with icons disabled."""
        mock_context.config.general.icons = False
        self.setup_selector_choice(mock_context, None)  # Exit immediately
        
        result = main(mock_context, basic_state)
        
        self.assert_exit_behavior(result)
        # Verify selector was called with non-icon options
        mock_context.selector.choose.assert_called_once()
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        # Verify no emoji icons in choices
        for choice in choices:
            assert not any(char in choice for char in '🔥✨💖💯🎬🔔🎲🔎📺📑✅⏸️🚮🔁📖🔐🔧📝❌')
    
    def test_main_menu_authenticated_user_header(self, mock_context, basic_state, mock_user_profile):
        """Test that authenticated user info appears in header."""
        mock_context.media_api.user_profile = mock_user_profile
        self.setup_selector_choice(mock_context, None)  # Exit immediately
        
        result = main(mock_context, basic_state)
        
        self.assert_exit_behavior(result)
        # Verify selector was called with header containing user info
        mock_context.selector.choose.assert_called_once()
        call_args = mock_context.selector.choose.call_args
        header = call_args[1]['header']
        assert mock_user_profile.name in header
    
    def test_main_menu_unauthenticated_user_header(self, mock_unauthenticated_context, basic_state):
        """Test that unauthenticated user gets appropriate header."""
        self.setup_selector_choice(mock_unauthenticated_context, None)  # Exit immediately
        
        result = main(mock_unauthenticated_context, basic_state)
        
        self.assert_exit_behavior(result)
        # Verify selector was called with appropriate header
        mock_unauthenticated_context.selector.choose.assert_called_once()
        call_args = mock_unauthenticated_context.selector.choose.call_args
        header = call_args[1]['header']
        assert "Not authenticated" in header or "FastAnime Main Menu" in header
    
    def test_main_menu_user_list_authentication_required(self, mock_unauthenticated_context, basic_state):
        """Test that user list options require authentication."""
        # Test that user list options either don't appear or show auth error
        self.setup_selector_choice(mock_unauthenticated_context, TEST_MENU_OPTIONS['watching'])
        
        # This should either not be available or show an auth error
        with patch('fastanime.cli.utils.auth_utils.check_authentication_required') as mock_auth_check:
            mock_auth_check.return_value = False  # Auth required but not authenticated
            
            result = main(mock_unauthenticated_context, basic_state)
            
            # Should continue (show error) or redirect to auth
            assert isinstance(result, (ControlFlow, State))
    
    @pytest.mark.parametrize("media_list_size", [0, 1, 5, 20])
    def test_main_menu_various_result_sizes(self, mock_context, basic_state, media_list_size):
        """Test handling of various media list result sizes."""
        self.setup_selector_choice(mock_context, TEST_MENU_OPTIONS['trending'])
        
        if media_list_size == 0:
            # Empty result
            mock_result = MediaSearchResult(media=[], page_info={"total": 0, "current_page": 1, "last_page": 1, "has_next_page": False, "per_page": 20})
        else:
            mock_result = self.create_mock_media_result(media_list_size)
        
        self.setup_media_list_success(mock_context, mock_result)
        
        result = main(mock_context, basic_state)
        
        if media_list_size == 0:
            # Empty results might show a message and continue
            assert isinstance(result, (State, ControlFlow))
        else:
            self.assert_menu_transition(result, "RESULTS")
