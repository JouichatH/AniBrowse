"""
Tests for the results menu functionality.
"""

import pytest
from unittest.mock import Mock, patch

from fastanime.cli.interactive.menus.results import results
from fastanime.cli.interactive.state import ControlFlow, State, MediaApiState
from fastanime.libs.api.types import MediaItem, MediaSearchResult, PageInfo, MediaTitle, MediaImage, Studio


class TestResultsMenu:
    """Test cases for the results menu."""

    def test_results_menu_no_search_results(self, mock_context, empty_state):
        """Test results menu with no search results."""
        # State with no search results
        state_no_results = State(
            menu_name="RESULTS",
            media_api=MediaApiState(search_results=None)
        )
        
        result = results(mock_context, state_no_results)
        
        # Should go back when no results
        assert result == ControlFlow.BACK

    def test_results_menu_empty_media_list(self, mock_context, empty_state):
        """Test results menu with empty media list."""
        # State with empty search results
        empty_search_results = MediaSearchResult(
            media=[],
            page_info=PageInfo(
                total=0,
                per_page=15,
                current_page=1,
                has_next_page=False
            )
        )
        state_empty_results = State(
            menu_name="RESULTS",
            media_api=MediaApiState(search_results=empty_search_results)
        )
        
        result = results(mock_context, state_empty_results)
        
        # Should go back when no media found
        assert result == ControlFlow.BACK

    def test_results_menu_display_anime_list(self, mock_context, state_with_media_api):
        """Test results menu displays anime list correctly."""
        mock_context.selector.choose.return_value = "Back"
        
        result = results(mock_context, state_with_media_api)
        
        # Should go back when "Back" is selected
        assert result == ControlFlow.BACK
        
        # Verify selector was called with anime choices
        mock_context.selector.choose.assert_called_once()
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        
        # Should contain Back option
        assert "Back" in choices
        # Should contain formatted anime titles
        assert len(choices) >= 2  # At least anime + Back

    def test_results_menu_select_anime(self, mock_context, state_with_media_api, sample_media_item):
        """Test selecting an anime from results."""
        # Mock the format function to return a predictable title
        with patch('fastanime.cli.interactive.menus.results._format_anime_choice') as mock_format:
            mock_format.return_value = "Test Anime"
            mock_context.selector.choose.return_value = "Test Anime"
            
            result = results(mock_context, state_with_media_api)
            
            # Should transition to MEDIA_ACTIONS state
            assert isinstance(result, State)
            assert result.menu_name == "MEDIA_ACTIONS"
            assert result.media_api.anime == sample_media_item

    def test_results_menu_pagination_next_page(self, mock_context, empty_state):
        """Test pagination - next page navigation."""
        # Create search results with next page available
        search_results = MediaSearchResult(
            media=[
                MediaItem(
                    id=1,
                    title={"english": "Test Anime", "romaji": "Test Anime"},
                    status="FINISHED",
                    episodes=12
                )
            ],
            page_info=PageInfo(
                total=30,
                per_page=15,
                current_page=1,
                has_next_page=True
            )
        )
        
        state_with_pagination = State(
            menu_name="RESULTS",
            media_api=MediaApiState(search_results=search_results)
        )
        
        mock_context.selector.choose.return_value = "Next Page (Page 2)"
        
        with patch('fastanime.cli.interactive.menus.results._handle_pagination') as mock_pagination:
            mock_pagination.return_value = State(menu_name="RESULTS")
            
            result = results(mock_context, state_with_pagination)
            
            # Should call pagination handler
            mock_pagination.assert_called_once_with(mock_context, state_with_pagination, 1)

    def test_results_menu_pagination_previous_page(self, mock_context, empty_state):
        """Test pagination - previous page navigation."""
        # Create search results on page 2
        search_results = MediaSearchResult(
            media=[
                MediaItem(
                    id=1,
                    title={"english": "Test Anime", "romaji": "Test Anime"},
                    status="FINISHED",
                    episodes=12
                )
            ],
            page_info=PageInfo(
                total=30,
                per_page=15,
                current_page=2,
                has_next_page=False
            )
        )
        
        state_with_pagination = State(
            menu_name="RESULTS",
            media_api=MediaApiState(search_results=search_results)
        )
        
        mock_context.selector.choose.return_value = "Previous Page (Page 1)"
        
        with patch('fastanime.cli.interactive.menus.results._handle_pagination') as mock_pagination:
            mock_pagination.return_value = State(menu_name="RESULTS")
            
            result = results(mock_context, state_with_pagination)
            
            # Should call pagination handler
            mock_pagination.assert_called_once_with(mock_context, state_with_pagination, -1)

    def test_results_menu_no_choice_made(self, mock_context, state_with_media_api):
        """Test results menu when no choice is made (exit)."""
        mock_context.selector.choose.return_value = None
        
        result = results(mock_context, state_with_media_api)
        
        assert result == ControlFlow.EXIT

    def test_results_menu_with_preview(self, mock_context, state_with_media_api):
        """Test results menu with preview enabled."""
        mock_context.config.general.preview = "text"
        mock_context.selector.choose.return_value = "Back"
        
        with patch('fastanime.cli.utils.previews.get_anime_preview') as mock_preview:
            mock_preview.return_value = "preview_command"
            
            result = results(mock_context, state_with_media_api)
            
            # Should call preview function when preview is enabled
            mock_preview.assert_called_once()
            
            # Verify preview was passed to selector
            call_args = mock_context.selector.choose.call_args
            assert call_args[1]['preview'] == "preview_command"

    def test_results_menu_no_preview(self, mock_context, state_with_media_api):
        """Test results menu with preview disabled."""
        mock_context.config.general.preview = "none"
        mock_context.selector.choose.return_value = "Back"
        
        result = results(mock_context, state_with_media_api)
        
        # Verify no preview was passed to selector
        call_args = mock_context.selector.choose.call_args
        assert call_args[1]['preview'] is None

    def test_results_menu_auth_status_display(self, mock_context, state_with_media_api):
        """Test that authentication status is displayed in header."""
        mock_context.selector.choose.return_value = "Back"
        
        with patch('fastanime.cli.interactive.menus.results.get_auth_status_indicator') as mock_auth:
            mock_auth.return_value = ("🟢 Authenticated", Mock())
            
            result = results(mock_context, state_with_media_api)
            
            # Should call auth status function
            mock_auth.assert_called_once_with(mock_context.media_api, mock_context.config.general.icons)
            
            # Verify header contains auth status
            call_args = mock_context.selector.choose.call_args
            header = call_args[1]['header']
            assert "🟢 Authenticated" in header

    def test_results_menu_pagination_info_in_header(self, mock_context, empty_state):
        """Test that pagination info is displayed in header."""
        search_results = MediaSearchResult(
            media=[
                MediaItem(
                    id=1,
                    title={"english": "Test Anime", "romaji": "Test Anime"},
                    status="FINISHED",
                    episodes=12
                )
            ],
            page_info=PageInfo(
                total=30,
                per_page=15,
                current_page=2,
                has_next_page=True
            )
        )
        
        state_with_pagination = State(
            menu_name="RESULTS",
            media_api=MediaApiState(search_results=search_results)
        )
        
        mock_context.selector.choose.return_value = "Back"
        
        with patch('fastanime.cli.interactive.menus.results.get_auth_status_indicator') as mock_auth:
            mock_auth.return_value = ("Auth Status", Mock())
            
            result = results(mock_context, state_with_pagination)
            
            # Verify header contains pagination info
            call_args = mock_context.selector.choose.call_args
            header = call_args[1]['header']
            assert "Page 2" in header
            assert "~2" in header  # Total pages

    def test_results_menu_unknown_choice_fallback(self, mock_context, state_with_media_api):
        """Test results menu with unknown choice returns CONTINUE."""
        mock_context.selector.choose.return_value = "Unknown Choice"
        
        with patch('fastanime.cli.interactive.menus.results._format_anime_choice') as mock_format:
            mock_format.return_value = "Test Anime"
            
            result = results(mock_context, state_with_media_api)
            
            # Should return CONTINUE for unknown choices
            assert result == ControlFlow.CONTINUE


class TestResultsMenuHelperFunctions:
    """Test the helper functions in results menu."""

    def test_format_anime_choice(self, mock_config, sample_media_item):
        """Test formatting anime choice for display."""
        from fastanime.cli.interactive.menus.results import _format_anime_choice
        
        # Test with English title preferred
        mock_config.anilist.preferred_language = "english"
        result = _format_anime_choice(sample_media_item, mock_config)
        
        assert "Test Anime" in result
        assert "12" in result  # Episode count

    def test_format_anime_choice_romaji(self, mock_config, sample_media_item):
        """Test formatting anime choice with romaji preference."""
        from fastanime.cli.interactive.menus.results import _format_anime_choice
        
        # Test with Romaji title preferred
        mock_config.anilist.preferred_language = "romaji"
        result = _format_anime_choice(sample_media_item, mock_config)
        
        assert "Test Anime" in result

    def test_format_anime_choice_no_episodes(self, mock_config):
        """Test formatting anime choice with no episode count."""
        from fastanime.cli.interactive.menus.results import _format_anime_choice
        
        anime_no_episodes = MediaItem(
            id=1,
            title={"english": "Test Anime", "romaji": "Test Anime"},
            status="FINISHED",
            episodes=None
        )
        
        result = _format_anime_choice(anime_no_episodes, mock_config)
        
        assert "Test Anime" in result
        assert "?" in result  # Unknown episode count

    def test_handle_pagination_next_page(self, mock_context, sample_media_item):
        """Test pagination handler for next page."""
        from fastanime.cli.interactive.menus.results import _handle_pagination
        from fastanime.libs.api.params import ApiSearchParams
        
        # Create a state with has_next_page=True and original API params
        state_with_next_page = State(
            menu_name="RESULTS",
            media_api=MediaApiState(
                search_results=MediaSearchResult(
                    media=[sample_media_item], 
                    page_info=PageInfo(total=25, per_page=15, current_page=1, has_next_page=True)
                ),
                original_api_params=ApiSearchParams(sort="TRENDING_DESC")
            )
        )
        
        # Mock API search parameters from state
        mock_context.media_api.search_media.return_value = MediaSearchResult(
            media=[], page_info=PageInfo(total=25, per_page=15, current_page=2, has_next_page=False)
        )
        
        with patch('fastanime.cli.interactive.menus.results.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, mock_context.media_api.search_media.return_value)
            
            result = _handle_pagination(mock_context, state_with_next_page, 1)
            
            # Should return new state with updated results
            assert isinstance(result, State)
            assert result.menu_name == "RESULTS"

    def test_handle_pagination_api_failure(self, mock_context, state_with_media_api):
        """Test pagination handler when API fails."""
        from fastanime.cli.interactive.menus.results import _handle_pagination
        
        with patch('fastanime.cli.interactive.menus.results.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (False, None)
            
            result = _handle_pagination(mock_context, state_with_media_api, 1)
            
            # Should return CONTINUE on API failure
            assert result == ControlFlow.CONTINUE

    def test_handle_pagination_user_list_params(self, mock_context, empty_state):
        """Test pagination with user list parameters."""
        from fastanime.cli.interactive.menus.results import _handle_pagination
        from fastanime.libs.api.params import UserListParams
        
        # State with user list params and has_next_page=True
        state_with_user_list = State(
            menu_name="RESULTS",
            media_api=MediaApiState(
                search_results=MediaSearchResult(
                    media=[], 
                    page_info=PageInfo(total=0, per_page=15, current_page=1, has_next_page=True)
                ),
                original_user_list_params=UserListParams(status="CURRENT", per_page=15)
            )
        )
        
        mock_context.media_api.fetch_user_list.return_value = MediaSearchResult(
            media=[], page_info=PageInfo(total=0, per_page=15, current_page=2, has_next_page=False)
        )
        
        with patch('fastanime.cli.interactive.menus.results.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, mock_context.media_api.fetch_user_list.return_value)
            
            result = _handle_pagination(mock_context, state_with_user_list, 1)
            
            # Should call fetch_user_list instead of search_media
            assert isinstance(result, State)
            assert result.menu_name == "RESULTS"
