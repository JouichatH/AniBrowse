"""
Tests for the results menu.
Tests anime result display, pagination, and selection.
"""

import pytest
from unittest.mock import Mock, patch

from fastanime.cli.interactive.menus.results import results
from fastanime.cli.interactive.state import State, ControlFlow, MediaApiState

from .base_test import BaseMenuTest, MediaMenuTestMixin


class TestResultsMenu(BaseMenuTest, MediaMenuTestMixin):
    """Test cases for the results menu."""
    
    def test_results_menu_no_results_goes_back(self, mock_context, basic_state):
        """Test that no results returns BACK."""
        # State with no search results
        state_no_results = State(
            menu_name="RESULTS",
            media_api=MediaApiState(search_results=None)
        )
        
        result = results(mock_context, state_no_results)
        
        self.assert_back_behavior(result)
        self.assert_console_cleared()
    
    def test_results_menu_empty_results_goes_back(self, mock_context, basic_state):
        """Test that empty results returns BACK."""
        # State with empty search results
        from fastanime.libs.api.types import MediaSearchResult
        
        empty_results = MediaSearchResult(
            media=[],
            page_info={"total": 0, "current_page": 1, "last_page": 1, "has_next_page": False, "per_page": 20}
        )
        
        state_empty = State(
            menu_name="RESULTS",
            media_api=MediaApiState(search_results=empty_results)
        )
        
        result = results(mock_context, state_empty)
        
        self.assert_back_behavior(result)
        self.assert_console_cleared()
    
    def test_results_menu_no_choice_goes_back(self, mock_context, state_with_media_data):
        """Test that no choice selected results in BACK."""
        self.setup_selector_choice(mock_context, None)
        
        result = results(mock_context, state_with_media_data)
        
        self.assert_back_behavior(result)
        self.assert_console_cleared()
    
    def test_results_menu_back_choice(self, mock_context, state_with_media_data):
        """Test explicit back choice."""
        self.setup_selector_choice(mock_context, "↩️ Back")
        
        result = results(mock_context, state_with_media_data)
        
        self.assert_back_behavior(result)
        self.assert_console_cleared()
    
    def test_results_menu_anime_selection(self, mock_context, state_with_media_data, mock_media_item):
        """Test selecting an anime transitions to media actions."""
        # Mock formatted anime title choice
        formatted_title = f"{mock_media_item.title} ({mock_media_item.status})"
        self.setup_selector_choice(mock_context, formatted_title)
        
        with patch('fastanime.cli.interactive.menus.results._format_anime_choice', return_value=formatted_title):
            result = results(mock_context, state_with_media_data)
            
            self.assert_menu_transition(result, "MEDIA_ACTIONS")
            self.assert_console_cleared()
            # Verify the selected anime is stored in the new state
            assert result.media_api.anime == mock_media_item
    
    def test_results_menu_next_page_navigation(self, mock_context, mock_media_search_result):
        """Test next page navigation."""
        # Create results with next page available
        mock_media_search_result.page_info["has_next_page"] = True
        mock_media_search_result.page_info["current_page"] = 1
        
        state_with_pagination = State(
            menu_name="RESULTS",
            media_api=MediaApiState(
                search_results=mock_media_search_result,
                original_api_params=Mock()
            )
        )
        
        self.setup_selector_choice(mock_context, "➡️ Next Page (Page 2)")
        mock_context.media_api.search_media.return_value = mock_media_search_result
        
        result = results(mock_context, state_with_pagination)
        
        self.assert_menu_transition(result, "RESULTS")
        self.assert_console_cleared()
        # Verify API was called for next page
        mock_context.media_api.search_media.assert_called_once()
    
    def test_results_menu_previous_page_navigation(self, mock_context, mock_media_search_result):
        """Test previous page navigation."""
        # Create results with previous page available
        mock_media_search_result.page_info["has_next_page"] = False
        mock_media_search_result.page_info["current_page"] = 2
        
        state_with_pagination = State(
            menu_name="RESULTS",
            media_api=MediaApiState(
                search_results=mock_media_search_result,
                original_api_params=Mock()
            )
        )
        
        self.setup_selector_choice(mock_context, "⬅️ Previous Page (Page 1)")
        mock_context.media_api.search_media.return_value = mock_media_search_result
        
        result = results(mock_context, state_with_pagination)
        
        self.assert_menu_transition(result, "RESULTS")
        self.assert_console_cleared()
        # Verify API was called for previous page
        mock_context.media_api.search_media.assert_called_once()
    
    def test_results_menu_pagination_failure(self, mock_context, mock_media_search_result):
        """Test pagination request failure."""
        mock_media_search_result.page_info["has_next_page"] = True
        mock_media_search_result.page_info["current_page"] = 1
        
        state_with_pagination = State(
            menu_name="RESULTS",
            media_api=MediaApiState(
                search_results=mock_media_search_result,
                original_api_params=Mock()
            )
        )
        
        self.setup_selector_choice(mock_context, "➡️ Next Page (Page 2)")
        mock_context.media_api.search_media.return_value = None  # Pagination fails
        
        result = results(mock_context, state_with_pagination)
        
        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        self.assert_feedback_error_called("Failed to load")
    
    def test_results_menu_icons_disabled(self, mock_context, state_with_media_data):
        """Test menu display with icons disabled."""
        mock_context.config.general.icons = False
        self.setup_selector_choice(mock_context, None)
        
        result = results(mock_context, state_with_media_data)
        
        self.assert_back_behavior(result)
        # Verify options don't contain emoji icons
        mock_context.selector.choose.assert_called_once()
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        
        # Navigation choices should not have emoji
        navigation_choices = [choice for choice in choices if "Page" in choice or "Back" in choice]
        for choice in navigation_choices:
            assert not any(char in choice for char in '➡️⬅️↩️')
    
    def test_results_menu_preview_enabled(self, mock_context, state_with_media_data):
        """Test that preview is set up when enabled."""
        mock_context.config.general.preview = "image"
        self.setup_selector_choice(mock_context, None)
        
        with patch('fastanime.cli.utils.previews.get_anime_preview') as mock_preview:
            mock_preview.return_value = "preview_command"
            
            result = results(mock_context, state_with_media_data)
            
            self.assert_back_behavior(result)
            # Verify preview was set up
            mock_preview.assert_called_once()
    
    def test_results_menu_preview_disabled(self, mock_context, state_with_media_data):
        """Test that preview is not set up when disabled."""
        mock_context.config.general.preview = "none"
        self.setup_selector_choice(mock_context, None)
        
        with patch('fastanime.cli.utils.previews.get_anime_preview') as mock_preview:
            result = results(mock_context, state_with_media_data)
            
            self.assert_back_behavior(result)
            # Verify preview was not set up
            mock_preview.assert_not_called()
    
    def test_results_menu_new_search_option(self, mock_context, state_with_media_data):
        """Test new search option."""
        self.setup_selector_choice(mock_context, "🔍 New Search")
        
        result = results(mock_context, state_with_media_data)
        
        self.assert_menu_transition(result, "PROVIDER_SEARCH")
        self.assert_console_cleared()
    
    def test_results_menu_sort_and_filter_option(self, mock_context, state_with_media_data):
        """Test sort and filter option."""
        self.setup_selector_choice(mock_context, "🔧 Sort & Filter")
        
        result = results(mock_context, state_with_media_data)
        
        self.assert_continue_behavior(result)  # Usually shows sort/filter submenu
        self.assert_console_cleared()
    
    @pytest.mark.parametrize("num_results", [1, 5, 20, 50])
    def test_results_menu_various_result_counts(self, mock_context, basic_state, num_results):
        """Test handling of various result counts."""
        mock_result = self.create_mock_media_result(num_results)
        
        state_with_results = State(
            menu_name="RESULTS",
            media_api=MediaApiState(search_results=mock_result)
        )
        
        self.setup_selector_choice(mock_context, None)
        
        result = results(mock_context, state_with_results)
        
        if num_results > 0:
            self.assert_back_behavior(result)
            # Verify choices include all anime titles
            mock_context.selector.choose.assert_called_once()
            call_args = mock_context.selector.choose.call_args
            choices = call_args[1]['choices']
            # Should have anime choices plus navigation options
            assert len([c for c in choices if "Page" not in c and "Back" not in c and "Search" not in c]) >= num_results
        else:
            self.assert_back_behavior(result)
    
    def test_results_menu_pagination_edge_cases(self, mock_context, mock_media_search_result):
        """Test pagination edge cases (first page, last page)."""
        # Test first page (no previous page option)
        mock_media_search_result.page_info["current_page"] = 1
        mock_media_search_result.page_info["has_next_page"] = True
        
        state_first_page = State(
            menu_name="RESULTS",
            media_api=MediaApiState(search_results=mock_media_search_result)
        )
        
        self.setup_selector_choice(mock_context, None)
        
        result = results(mock_context, state_first_page)
        
        self.assert_back_behavior(result)
        mock_context.selector.choose.assert_called_once()
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        
        # Should have next page but no previous page
        assert any("Next Page" in choice for choice in choices)
        assert not any("Previous Page" in choice for choice in choices)
    
    def test_results_menu_last_page(self, mock_context, mock_media_search_result):
        """Test last page (no next page option)."""
        mock_media_search_result.page_info["current_page"] = 5
        mock_media_search_result.page_info["has_next_page"] = False
        
        state_last_page = State(
            menu_name="RESULTS",
            media_api=MediaApiState(search_results=mock_media_search_result)
        )
        
        self.setup_selector_choice(mock_context, None)
        
        result = results(mock_context, state_last_page)
        
        self.assert_back_behavior(result)
        mock_context.selector.choose.assert_called_once()
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        
        # Should have previous page but no next page
        assert any("Previous Page" in choice for choice in choices)
        assert not any("Next Page" in choice for choice in choices)
    
    def test_results_menu_anime_formatting(self, mock_context, state_with_media_data, mock_media_item):
        """Test anime choice formatting."""
        self.setup_selector_choice(mock_context, None)
        
        with patch('fastanime.cli.interactive.menus.results._format_anime_choice') as mock_format:
            expected_format = f"{mock_media_item.title} ({mock_media_item.status}) - Score: {mock_media_item.mean_score}"
            mock_format.return_value = expected_format
            
            result = results(mock_context, state_with_media_data)
            
            self.assert_back_behavior(result)
            # Verify formatting function was called
            mock_format.assert_called_once()
    
    def test_results_menu_auth_status_in_header(self, mock_context, state_with_media_data, mock_user_profile):
        """Test that auth status appears in header."""
        mock_context.media_api.user_profile = mock_user_profile
        self.setup_selector_choice(mock_context, None)
        
        with patch('fastanime.cli.utils.auth_utils.get_auth_status_indicator') as mock_auth_status:
            mock_auth_status.return_value = f"👤 {mock_user_profile.name}"
            
            result = results(mock_context, state_with_media_data)
            
            self.assert_back_behavior(result)
            # Verify auth status was included
            mock_auth_status.assert_called_once()
    
    def test_results_menu_error_handling_during_selection(self, mock_context, state_with_media_data):
        """Test error handling during anime selection."""
        self.setup_selector_choice(mock_context, "Invalid Choice")
        
        result = results(mock_context, state_with_media_data)
        
        # Should handle invalid choice gracefully
        assert isinstance(result, (State, ControlFlow))
        self.assert_console_cleared()
    
    def test_results_menu_user_list_context(self, mock_context, mock_media_search_result):
        """Test results from user list context."""
        # State indicating results came from user list
        state_user_list = State(
            menu_name="RESULTS",
            media_api=MediaApiState(
                search_results=mock_media_search_result,
                search_results_type="USER_MEDIA_LIST",
                user_media_status="WATCHING"
            )
        )
        
        self.setup_selector_choice(mock_context, None)
        
        result = results(mock_context, state_user_list)
        
        self.assert_back_behavior(result)
        # Header should indicate this is a user list
        mock_context.selector.choose.assert_called_once()
        call_args = mock_context.selector.choose.call_args
        header = call_args[1].get('header', '')
        # Should contain user list context information
