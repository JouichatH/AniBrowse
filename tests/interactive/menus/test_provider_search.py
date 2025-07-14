"""
Tests for the provider search menu functionality.
"""

import pytest
from unittest.mock import Mock, patch

from fastanime.cli.interactive.menus.provider_search import provider_search
from fastanime.cli.interactive.state import ControlFlow, State, MediaApiState, ProviderState
from fastanime.libs.providers.anime.types import Anime, SearchResults
from fastanime.libs.api.types import MediaItem


class TestProviderSearchMenu:
    """Test cases for the provider search menu."""

    def test_provider_search_no_anilist_anime(self, mock_context, empty_state):
        """Test provider search with no AniList anime selected."""
        result = provider_search(mock_context, empty_state)
        
        # Should go back when no anime is selected
        assert result == ControlFlow.BACK

    def test_provider_search_no_title(self, mock_context, empty_state):
        """Test provider search with anime having no title."""
        # Create anime with no title
        anime_no_title = MediaItem(
            id=1,
            title={"english": None, "romaji": None},
            status="FINISHED",
            episodes=12
        )
        
        state_no_title = State(
            menu_name="PROVIDER_SEARCH",
            media_api=MediaApiState(anime=anime_no_title)
        )
        
        result = provider_search(mock_context, state_no_title)
        
        # Should go back when anime has no searchable title
        assert result == ControlFlow.BACK

    def test_provider_search_successful_search(self, mock_context, state_with_media_api):
        """Test successful provider search with results."""
        # Mock provider search results
        search_results = SearchResults(
            anime=[
                Anime(
                    name="Test Anime",
                    url="https://example.com/anime1",
                    id="anime1",
                    poster="https://example.com/poster1.jpg"
                ),
                Anime(
                    name="Test Anime Season 2",
                    url="https://example.com/anime2",
                    id="anime2",
                    poster="https://example.com/poster2.jpg"
                )
            ]
        )
        
        # Mock user selection
        mock_context.selector.choose.return_value = "Test Anime"
        
        with patch('fastanime.cli.interactive.menus.provider_search.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, search_results)
            
            result = provider_search(mock_context, state_with_media_api)
            
            # Should transition to EPISODES state
            assert isinstance(result, State)
            assert result.menu_name == "EPISODES"
            assert result.provider.anime.name == "Test Anime"

    def test_provider_search_no_results(self, mock_context, state_with_media_api):
        """Test provider search with no results."""
        # Mock empty search results
        empty_results = SearchResults(anime=[])
        
        with patch('fastanime.cli.interactive.menus.provider_search.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, empty_results)
            
            result = provider_search(mock_context, state_with_media_api)
            
            # Should go back when no results found
            assert result == ControlFlow.BACK

    def test_provider_search_api_failure(self, mock_context, state_with_media_api):
        """Test provider search when API fails."""
        with patch('fastanime.cli.interactive.menus.provider_search.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (False, None)
            
            result = provider_search(mock_context, state_with_media_api)
            
            # Should go back when API fails
            assert result == ControlFlow.BACK

    def test_provider_search_auto_select_enabled(self, mock_context, state_with_media_api):
        """Test provider search with auto select enabled."""
        # Enable auto select in config
        mock_context.config.general.auto_select_anime_result = True
        
        # Mock search results with high similarity match
        search_results = SearchResults(
            anime=[
                Anime(
                    name="Test Anime",  # Exact match with AniList title
                    url="https://example.com/anime1",
                    id="anime1",
                    poster="https://example.com/poster1.jpg"
                )
            ]
        )
        
        with patch('fastanime.cli.interactive.menus.provider_search.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, search_results)
            
            with patch('fastanime.cli.interactive.menus.provider_search.fuzz.ratio') as mock_fuzz:
                mock_fuzz.return_value = 95  # High similarity score
                
                result = provider_search(mock_context, state_with_media_api)
                
                # Should auto-select and transition to EPISODES
                assert isinstance(result, State)
                assert result.menu_name == "EPISODES"
                
                # Selector should not be called for auto selection
                mock_context.selector.choose.assert_not_called()

    def test_provider_search_auto_select_low_similarity(self, mock_context, state_with_media_api):
        """Test provider search with auto select but low similarity."""
        # Enable auto select in config
        mock_context.config.general.auto_select_anime_result = True
        
        # Mock search results with low similarity
        search_results = SearchResults(
            anime=[
                Anime(
                    name="Different Anime",
                    url="https://example.com/anime1",
                    id="anime1",
                    poster="https://example.com/poster1.jpg"
                )
            ]
        )
        
        mock_context.selector.choose.return_value = "Different Anime"
        
        with patch('fastanime.cli.interactive.menus.provider_search.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, search_results)
            
            with patch('fastanime.cli.interactive.menus.provider_search.fuzz.ratio') as mock_fuzz:
                mock_fuzz.return_value = 60  # Low similarity score
                
                result = provider_search(mock_context, state_with_media_api)
                
                # Should show manual selection
                mock_context.selector.choose.assert_called_once()
                assert isinstance(result, State)
                assert result.menu_name == "EPISODES"

    def test_provider_search_manual_selection_cancelled(self, mock_context, state_with_media_api):
        """Test provider search when manual selection is cancelled."""
        # Disable auto select
        mock_context.config.general.auto_select_anime_result = False
        
        search_results = SearchResults(
            anime=[
                Anime(
                    name="Test Anime",
                    url="https://example.com/anime1",
                    id="anime1",
                    poster="https://example.com/poster1.jpg"
                )
            ]
        )
        
        # Mock cancelled selection
        mock_context.selector.choose.return_value = None
        
        with patch('fastanime.cli.interactive.menus.provider_search.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, search_results)
            
            result = provider_search(mock_context, state_with_media_api)
            
            # Should go back when selection is cancelled
            assert result == ControlFlow.BACK

    def test_provider_search_back_selection(self, mock_context, state_with_media_api):
        """Test provider search back selection."""
        search_results = SearchResults(
            anime=[
                Anime(
                    name="Test Anime",
                    url="https://example.com/anime1",
                    id="anime1",
                    poster="https://example.com/poster1.jpg"
                )
            ]
        )
        
        # Mock back selection
        mock_context.selector.choose.return_value = "Back"
        
        with patch('fastanime.cli.interactive.menus.provider_search.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, search_results)
            
            result = provider_search(mock_context, state_with_media_api)
            
            # Should go back
            assert result == ControlFlow.BACK

    def test_provider_search_invalid_selection(self, mock_context, state_with_media_api):
        """Test provider search with invalid selection."""
        search_results = SearchResults(
            anime=[
                Anime(
                    name="Test Anime",
                    url="https://example.com/anime1",
                    id="anime1",
                    poster="https://example.com/poster1.jpg"
                )
            ]
        )
        
        # Mock invalid selection (not in results)
        mock_context.selector.choose.return_value = "Invalid Anime"
        
        with patch('fastanime.cli.interactive.menus.provider_search.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, search_results)
            
            result = provider_search(mock_context, state_with_media_api)
            
            # Should go back for invalid selection
            assert result == ControlFlow.BACK

    def test_provider_search_with_preview(self, mock_context, state_with_media_api):
        """Test provider search with preview enabled."""
        mock_context.config.general.preview = "text"
        
        search_results = SearchResults(
            anime=[
                Anime(
                    name="Test Anime",
                    url="https://example.com/anime1",
                    id="anime1",
                    poster="https://example.com/poster1.jpg"
                )
            ]
        )
        
        mock_context.selector.choose.return_value = "Test Anime"
        
        with patch('fastanime.cli.interactive.menus.provider_search.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, search_results)
            
            with patch('fastanime.cli.interactive.menus.provider_search.get_anime_preview') as mock_preview:
                mock_preview.return_value = "preview_command"
                
                result = provider_search(mock_context, state_with_media_api)
                
                # Should call preview function
                mock_preview.assert_called_once()
                
                # Verify preview was passed to selector
                call_args = mock_context.selector.choose.call_args
                assert call_args[1]['preview'] == "preview_command"

    def test_provider_search_english_title_preference(self, mock_context, empty_state):
        """Test provider search using English title when available."""
        # Create anime with both English and Romaji titles
        anime_dual_titles = MediaItem(
            id=1,
            title={"english": "English Title", "romaji": "Romaji Title"},
            status="FINISHED",
            episodes=12
        )
        
        state_dual_titles = State(
            menu_name="PROVIDER_SEARCH",
            media_api=MediaApiState(anime=anime_dual_titles)
        )
        
        search_results = SearchResults(
            anime=[
                Anime(
                    name="English Title",
                    url="https://example.com/anime1",
                    id="anime1",
                    poster="https://example.com/poster1.jpg"
                )
            ]
        )
        
        with patch('fastanime.cli.interactive.menus.provider_search.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, search_results)
            
            mock_context.selector.choose.return_value = "English Title"
            
            result = provider_search(mock_context, state_dual_titles)
            
            # Should search using English title
            mock_context.provider.search.assert_called_once()
            search_params = mock_context.provider.search.call_args[0][0]
            assert search_params.query == "English Title"

    def test_provider_search_romaji_title_fallback(self, mock_context, empty_state):
        """Test provider search falling back to Romaji title when English not available."""
        # Create anime with only Romaji title
        anime_romaji_only = MediaItem(
            id=1,
            title={"english": None, "romaji": "Romaji Title"},
            status="FINISHED",
            episodes=12
        )
        
        state_romaji_only = State(
            menu_name="PROVIDER_SEARCH",
            media_api=MediaApiState(anime=anime_romaji_only)
        )
        
        search_results = SearchResults(
            anime=[
                Anime(
                    name="Romaji Title",
                    url="https://example.com/anime1",
                    id="anime1",
                    poster="https://example.com/poster1.jpg"
                )
            ]
        )
        
        with patch('fastanime.cli.interactive.menus.provider_search.execute_with_feedback') as mock_execute:
            mock_execute.return_value = (True, search_results)
            
            mock_context.selector.choose.return_value = "Romaji Title"
            
            result = provider_search(mock_context, state_romaji_only)
            
            # Should search using Romaji title
            mock_context.provider.search.assert_called_once()
            search_params = mock_context.provider.search.call_args[0][0]
            assert search_params.query == "Romaji Title"


class TestProviderSearchHelperFunctions:
    """Test the helper functions in provider search menu."""

    def test_format_provider_anime_choice(self, mock_config):
        """Test formatting provider anime choice for display."""
        from fastanime.cli.interactive.menus.provider_search import _format_provider_anime_choice
        
        anime = Anime(
            name="Test Anime",
            url="https://example.com/anime1",
            id="anime1",
            poster="https://example.com/poster1.jpg"
        )
        
        mock_config.general.icons = True
        
        result = _format_provider_anime_choice(anime, mock_config)
        
        assert "Test Anime" in result

    def test_format_provider_anime_choice_no_icons(self, mock_config):
        """Test formatting provider anime choice without icons."""
        from fastanime.cli.interactive.menus.provider_search import _format_provider_anime_choice
        
        anime = Anime(
            name="Test Anime",
            url="https://example.com/anime1",
            id="anime1",
            poster="https://example.com/poster1.jpg"
        )
        
        mock_config.general.icons = False
        
        result = _format_provider_anime_choice(anime, mock_config)
        
        assert "Test Anime" in result
        assert "📺" not in result  # No icons should be present

    def test_get_best_match_high_similarity(self):
        """Test getting best match with high similarity."""
        from fastanime.cli.interactive.menus.provider_search import _get_best_match
        
        anilist_title = "Test Anime"
        search_results = SearchResults(
            anime=[
                Anime(name="Test Anime", url="https://example.com/1", id="1", poster=""),
                Anime(name="Different Anime", url="https://example.com/2", id="2", poster="")
            ]
        )
        
        with patch('fastanime.cli.interactive.menus.provider_search.fuzz.ratio') as mock_fuzz:
            mock_fuzz.side_effect = [95, 60]  # High similarity for first anime
            
            result = _get_best_match(anilist_title, search_results, threshold=80)
            
            assert result.name == "Test Anime"

    def test_get_best_match_low_similarity(self):
        """Test getting best match with low similarity."""
        from fastanime.cli.interactive.menus.provider_search import _get_best_match
        
        anilist_title = "Test Anime"
        search_results = SearchResults(
            anime=[
                Anime(name="Different Show", url="https://example.com/1", id="1", poster=""),
                Anime(name="Another Show", url="https://example.com/2", id="2", poster="")
            ]
        )
        
        with patch('fastanime.cli.interactive.menus.provider_search.fuzz.ratio') as mock_fuzz:
            mock_fuzz.side_effect = [60, 50]  # Low similarity for all
            
            result = _get_best_match(anilist_title, search_results, threshold=80)
            
            assert result is None

    def test_get_best_match_empty_results(self):
        """Test getting best match with empty results."""
        from fastanime.cli.interactive.menus.provider_search import _get_best_match
        
        anilist_title = "Test Anime"
        empty_results = SearchResults(anime=[])
        
        result = _get_best_match(anilist_title, empty_results, threshold=80)
        
        assert result is None

    def test_should_auto_select_enabled_high_similarity(self, mock_config):
        """Test should auto select when enabled and high similarity."""
        from fastanime.cli.interactive.menus.provider_search import _should_auto_select
        
        mock_config.general.auto_select_anime_result = True
        best_match = Anime(name="Test Anime", url="https://example.com/1", id="1", poster="")
        
        result = _should_auto_select(mock_config, best_match)
        
        assert result is True

    def test_should_auto_select_disabled(self, mock_config):
        """Test should not auto select when disabled."""
        from fastanime.cli.interactive.menus.provider_search import _should_auto_select
        
        mock_config.general.auto_select_anime_result = False
        best_match = Anime(name="Test Anime", url="https://example.com/1", id="1", poster="")
        
        result = _should_auto_select(mock_config, best_match)
        
        assert result is False

    def test_should_auto_select_no_match(self, mock_config):
        """Test should not auto select when no good match."""
        from fastanime.cli.interactive.menus.provider_search import _should_auto_select
        
        mock_config.general.auto_select_anime_result = True
        
        result = _should_auto_select(mock_config, None)
        
        assert result is False
