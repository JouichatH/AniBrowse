"""
Tests for the watch history menu functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from fastanime.cli.interactive.menus.watch_history import watch_history
from fastanime.cli.interactive.state import ControlFlow, State, MediaApiState
from fastanime.libs.api.types import MediaItem


class TestWatchHistoryMenu:
    """Test cases for the watch history menu."""

    def test_watch_history_menu_display(self, mock_context, empty_state):
        """Test that watch history menu displays correctly."""
        mock_context.selector.choose.return_value = "🔙 Back to Main Menu"
        
        # Mock watch history
        mock_history = [
            {
                "anilist_id": 1,
                "title": "Test Anime 1",
                "last_watched": "2023-01-01 12:00:00",
                "episode": 5,
                "total_episodes": 12
            },
            {
                "anilist_id": 2,
                "title": "Test Anime 2",
                "last_watched": "2023-01-02 13:00:00",
                "episode": 3,
                "total_episodes": 24
            }
        ]
        
        with patch('fastanime.cli.interactive.menus.watch_history.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_history
            
            result = watch_history(mock_context, empty_state)
            
            # Should go back when "Back to Main Menu" is selected
            assert result == ControlFlow.BACK
            
            # Verify selector was called with history items
            mock_context.selector.choose.assert_called_once()
            call_args = mock_context.selector.choose.call_args
            choices = call_args[1]['choices']
            
            # Should contain anime from history plus control options
            history_items = [choice for choice in choices if "Test Anime" in choice]
            assert len(history_items) == 2

    def test_watch_history_menu_empty_history(self, mock_context, empty_state):
        """Test watch history menu with empty history."""
        with patch('fastanime.cli.interactive.menus.watch_history.get_watch_history') as mock_get_history:
            mock_get_history.return_value = []
            
            with patch('fastanime.cli.interactive.menus.watch_history.create_feedback_manager') as mock_feedback:
                feedback_obj = Mock()
                mock_feedback.return_value = feedback_obj
                
                result = watch_history(mock_context, empty_state)
                
                # Should show info message and go back
                feedback_obj.info.assert_called_once()
                assert result == ControlFlow.BACK

    def test_watch_history_select_anime(self, mock_context, empty_state):
        """Test selecting an anime from watch history."""
        mock_history = [
            {
                "anilist_id": 1,
                "title": "Test Anime 1",
                "last_watched": "2023-01-01 12:00:00",
                "episode": 5,
                "total_episodes": 12
            }
        ]
        
        # Mock AniList anime lookup
        mock_anime = MediaItem(
            id=1,
            title={"english": "Test Anime 1", "romaji": "Test Anime 1"},
            status="FINISHED",
            episodes=12
        )
        
        with patch('fastanime.cli.interactive.menus.watch_history.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_history
            
            with patch('fastanime.cli.interactive.menus.watch_history._format_history_item') as mock_format:
                mock_format.return_value = "Test Anime 1 - Episode 5/12"
                mock_context.selector.choose.return_value = "Test Anime 1 - Episode 5/12"
                
                # Mock successful AniList lookup
                mock_context.media_api.get_media_by_id.return_value = mock_anime
                
                result = watch_history(mock_context, empty_state)
                
                # Should transition to MEDIA_ACTIONS state
                assert isinstance(result, State)
                assert result.menu_name == "MEDIA_ACTIONS"
                assert result.media_api.anime == mock_anime

    def test_watch_history_anime_lookup_failure(self, mock_context, empty_state):
        """Test watch history when anime lookup fails."""
        mock_history = [
            {
                "anilist_id": 1,
                "title": "Test Anime 1",
                "last_watched": "2023-01-01 12:00:00",
                "episode": 5,
                "total_episodes": 12
            }
        ]
        
        with patch('fastanime.cli.interactive.menus.watch_history.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_history
            
            with patch('fastanime.cli.interactive.menus.watch_history._format_history_item') as mock_format:
                mock_format.return_value = "Test Anime 1 - Episode 5/12"
                mock_context.selector.choose.return_value = "Test Anime 1 - Episode 5/12"
                
                # Mock failed AniList lookup
                mock_context.media_api.get_media_by_id.return_value = None
                
                with patch('fastanime.cli.interactive.menus.watch_history.create_feedback_manager') as mock_feedback:
                    feedback_obj = Mock()
                    mock_feedback.return_value = feedback_obj
                    
                    result = watch_history(mock_context, empty_state)
                    
                    # Should show error and continue
                    feedback_obj.error.assert_called_once()
                    assert result == ControlFlow.CONTINUE

    def test_watch_history_clear_history(self, mock_context, empty_state):
        """Test clearing watch history."""
        mock_history = [
            {
                "anilist_id": 1,
                "title": "Test Anime 1",
                "last_watched": "2023-01-01 12:00:00",
                "episode": 5,
                "total_episodes": 12
            }
        ]
        
        with patch('fastanime.cli.interactive.menus.watch_history.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_history
            
            mock_context.selector.choose.return_value = "🗑️ Clear History"
            
            with patch('fastanime.cli.interactive.menus.watch_history.create_feedback_manager') as mock_feedback:
                feedback_obj = Mock()
                feedback_obj.confirm.return_value = True
                mock_feedback.return_value = feedback_obj
                
                with patch('fastanime.cli.interactive.menus.watch_history.clear_watch_history') as mock_clear:
                    result = watch_history(mock_context, empty_state)
                    
                    # Should clear history and continue
                    mock_clear.assert_called_once()
                    feedback_obj.success.assert_called_once()
                    assert result == ControlFlow.CONTINUE

    def test_watch_history_clear_history_cancelled(self, mock_context, empty_state):
        """Test clearing watch history when cancelled."""
        mock_history = [
            {
                "anilist_id": 1,
                "title": "Test Anime 1",
                "last_watched": "2023-01-01 12:00:00",
                "episode": 5,
                "total_episodes": 12
            }
        ]
        
        with patch('fastanime.cli.interactive.menus.watch_history.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_history
            
            mock_context.selector.choose.return_value = "🗑️ Clear History"
            
            with patch('fastanime.cli.interactive.menus.watch_history.create_feedback_manager') as mock_feedback:
                feedback_obj = Mock()
                feedback_obj.confirm.return_value = False  # User cancels
                mock_feedback.return_value = feedback_obj
                
                result = watch_history(mock_context, empty_state)
                
                # Should not clear and continue
                assert result == ControlFlow.CONTINUE

    def test_watch_history_export_history(self, mock_context, empty_state):
        """Test exporting watch history."""
        mock_history = [
            {
                "anilist_id": 1,
                "title": "Test Anime 1",
                "last_watched": "2023-01-01 12:00:00",
                "episode": 5,
                "total_episodes": 12
            }
        ]
        
        with patch('fastanime.cli.interactive.menus.watch_history.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_history
            
            mock_context.selector.choose.return_value = "📤 Export History"
            mock_context.selector.ask.return_value = "/path/to/export.json"
            
            with patch('fastanime.cli.interactive.menus.watch_history.export_watch_history') as mock_export:
                mock_export.return_value = True
                
                with patch('fastanime.cli.interactive.menus.watch_history.create_feedback_manager') as mock_feedback:
                    feedback_obj = Mock()
                    mock_feedback.return_value = feedback_obj
                    
                    result = watch_history(mock_context, empty_state)
                    
                    # Should export history and continue
                    mock_export.assert_called_once()
                    feedback_obj.success.assert_called_once()
                    assert result == ControlFlow.CONTINUE

    def test_watch_history_export_history_no_path(self, mock_context, empty_state):
        """Test exporting watch history with no path provided."""
        mock_history = [
            {
                "anilist_id": 1,
                "title": "Test Anime 1",
                "last_watched": "2023-01-01 12:00:00",
                "episode": 5,
                "total_episodes": 12
            }
        ]
        
        with patch('fastanime.cli.interactive.menus.watch_history.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_history
            
            mock_context.selector.choose.return_value = "📤 Export History"
            mock_context.selector.ask.return_value = ""  # Empty path
            
            result = watch_history(mock_context, empty_state)
            
            # Should continue without exporting
            assert result == ControlFlow.CONTINUE

    def test_watch_history_import_history(self, mock_context, empty_state):
        """Test importing watch history."""
        mock_history = []  # Start with empty history
        
        with patch('fastanime.cli.interactive.menus.watch_history.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_history
            
            mock_context.selector.choose.return_value = "📥 Import History"
            mock_context.selector.ask.return_value = "/path/to/import.json"
            
            with patch('fastanime.cli.interactive.menus.watch_history.import_watch_history') as mock_import:
                mock_import.return_value = True
                
                with patch('fastanime.cli.interactive.menus.watch_history.create_feedback_manager') as mock_feedback:
                    feedback_obj = Mock()
                    mock_feedback.return_value = feedback_obj
                    
                    result = watch_history(mock_context, empty_state)
                    
                    # Should import history and continue
                    mock_import.assert_called_once()
                    feedback_obj.success.assert_called_once()
                    assert result == ControlFlow.CONTINUE

    def test_watch_history_view_statistics(self, mock_context, empty_state):
        """Test viewing watch history statistics."""
        mock_history = [
            {
                "anilist_id": 1,
                "title": "Test Anime 1",
                "last_watched": "2023-01-01 12:00:00",
                "episode": 5,
                "total_episodes": 12
            },
            {
                "anilist_id": 2,
                "title": "Test Anime 2",
                "last_watched": "2023-01-02 13:00:00",
                "episode": 24,
                "total_episodes": 24
            }
        ]
        
        with patch('fastanime.cli.interactive.menus.watch_history.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_history
            
            mock_context.selector.choose.return_value = "📊 View Statistics"
            
            with patch('fastanime.cli.interactive.menus.watch_history.create_feedback_manager') as mock_feedback:
                feedback_obj = Mock()
                mock_feedback.return_value = feedback_obj
                
                result = watch_history(mock_context, empty_state)
                
                # Should display statistics and pause
                feedback_obj.pause_for_user.assert_called_once()
                assert result == ControlFlow.CONTINUE

    def test_watch_history_back_selection(self, mock_context, empty_state):
        """Test selecting back from watch history."""
        mock_history = [
            {
                "anilist_id": 1,
                "title": "Test Anime 1",
                "last_watched": "2023-01-01 12:00:00",
                "episode": 5,
                "total_episodes": 12
            }
        ]
        
        with patch('fastanime.cli.interactive.menus.watch_history.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_history
            
            mock_context.selector.choose.return_value = "🔙 Back to Main Menu"
            
            result = watch_history(mock_context, empty_state)
            
            assert result == ControlFlow.BACK

    def test_watch_history_no_choice(self, mock_context, empty_state):
        """Test watch history when no choice is made."""
        mock_history = [
            {
                "anilist_id": 1,
                "title": "Test Anime 1",
                "last_watched": "2023-01-01 12:00:00",
                "episode": 5,
                "total_episodes": 12
            }
        ]
        
        with patch('fastanime.cli.interactive.menus.watch_history.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_history
            
            mock_context.selector.choose.return_value = None
            
            result = watch_history(mock_context, empty_state)
            
            # Should go back when no choice is made
            assert result == ControlFlow.BACK

    def test_watch_history_invalid_selection(self, mock_context, empty_state):
        """Test watch history with invalid selection."""
        mock_history = [
            {
                "anilist_id": 1,
                "title": "Test Anime 1",
                "last_watched": "2023-01-01 12:00:00",
                "episode": 5,
                "total_episodes": 12
            }
        ]
        
        with patch('fastanime.cli.interactive.menus.watch_history.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_history
            
            with patch('fastanime.cli.interactive.menus.watch_history._format_history_item') as mock_format:
                mock_format.return_value = "Test Anime 1 - Episode 5/12"
                mock_context.selector.choose.return_value = "Invalid Selection"
                
                result = watch_history(mock_context, empty_state)
                
                # Should continue for invalid selection
                assert result == ControlFlow.CONTINUE

    def test_watch_history_icons_enabled(self, mock_context, empty_state):
        """Test watch history menu with icons enabled."""
        mock_context.config.general.icons = True
        
        mock_history = [
            {
                "anilist_id": 1,
                "title": "Test Anime 1",
                "last_watched": "2023-01-01 12:00:00",
                "episode": 5,
                "total_episodes": 12
            }
        ]
        
        with patch('fastanime.cli.interactive.menus.watch_history.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_history
            
            mock_context.selector.choose.return_value = "🔙 Back to Main Menu"
            
            result = watch_history(mock_context, empty_state)
            
            # Should work with icons enabled
            assert result == ControlFlow.BACK

    def test_watch_history_icons_disabled(self, mock_context, empty_state):
        """Test watch history menu with icons disabled."""
        mock_context.config.general.icons = False
        
        mock_history = [
            {
                "anilist_id": 1,
                "title": "Test Anime 1",
                "last_watched": "2023-01-01 12:00:00",
                "episode": 5,
                "total_episodes": 12
            }
        ]
        
        with patch('fastanime.cli.interactive.menus.watch_history.get_watch_history') as mock_get_history:
            mock_get_history.return_value = mock_history
            
            mock_context.selector.choose.return_value = "Back to Main Menu"
            
            result = watch_history(mock_context, empty_state)
            
            # Should work with icons disabled
            assert result == ControlFlow.BACK


class TestWatchHistoryHelperFunctions:
    """Test the helper functions in watch history menu."""

    def test_format_history_item(self):
        """Test formatting history item for display."""
        from fastanime.cli.interactive.menus.watch_history import _format_history_item
        
        history_item = {
            "anilist_id": 1,
            "title": "Test Anime",
            "last_watched": "2023-01-01 12:00:00",
            "episode": 5,
            "total_episodes": 12
        }
        
        result = _format_history_item(history_item, True)  # With icons
        
        assert "Test Anime" in result
        assert "5/12" in result  # Episode progress
        assert "2023-01-01" in result

    def test_format_history_item_no_icons(self):
        """Test formatting history item without icons."""
        from fastanime.cli.interactive.menus.watch_history import _format_history_item
        
        history_item = {
            "anilist_id": 1,
            "title": "Test Anime",
            "last_watched": "2023-01-01 12:00:00",
            "episode": 5,
            "total_episodes": 12
        }
        
        result = _format_history_item(history_item, False)  # Without icons
        
        assert "Test Anime" in result
        assert "📺" not in result  # No icons should be present

    def test_format_history_item_completed(self):
        """Test formatting completed anime in history."""
        from fastanime.cli.interactive.menus.watch_history import _format_history_item
        
        history_item = {
            "anilist_id": 1,
            "title": "Test Anime",
            "last_watched": "2023-01-01 12:00:00",
            "episode": 12,
            "total_episodes": 12
        }
        
        result = _format_history_item(history_item, True)
        
        assert "Test Anime" in result
        assert "12/12" in result  # Completed
        assert "✅" in result or "Completed" in result

    def test_calculate_watch_statistics(self):
        """Test calculating watch history statistics."""
        from fastanime.cli.interactive.menus.watch_history import _calculate_watch_statistics
        
        history = [
            {
                "anilist_id": 1,
                "title": "Test Anime 1",
                "episode": 12,
                "total_episodes": 12
            },
            {
                "anilist_id": 2,
                "title": "Test Anime 2",
                "episode": 5,
                "total_episodes": 24
            },
            {
                "anilist_id": 3,
                "title": "Test Anime 3",
                "episode": 1,
                "total_episodes": 12
            }
        ]
        
        stats = _calculate_watch_statistics(history)
        
        assert stats["total_anime"] == 3
        assert stats["completed_anime"] == 1
        assert stats["in_progress_anime"] == 2
        assert stats["total_episodes_watched"] == 18

    def test_calculate_watch_statistics_empty(self):
        """Test calculating statistics with empty history."""
        from fastanime.cli.interactive.menus.watch_history import _calculate_watch_statistics
        
        stats = _calculate_watch_statistics([])
        
        assert stats["total_anime"] == 0
        assert stats["completed_anime"] == 0
        assert stats["in_progress_anime"] == 0
        assert stats["total_episodes_watched"] == 0

    def test_display_watch_statistics(self):
        """Test displaying watch statistics."""
        from fastanime.cli.interactive.menus.watch_history import _display_watch_statistics
        
        console = Mock()
        stats = {
            "total_anime": 10,
            "completed_anime": 5,
            "in_progress_anime": 3,
            "total_episodes_watched": 120
        }
        
        _display_watch_statistics(console, stats, True)
        
        # Should print table with statistics
        console.print.assert_called()

    def test_get_history_item_by_selection(self):
        """Test getting history item by user selection."""
        from fastanime.cli.interactive.menus.watch_history import _get_history_item_by_selection
        
        history = [
            {
                "anilist_id": 1,
                "title": "Test Anime 1",
                "episode": 5,
                "total_episodes": 12
            },
            {
                "anilist_id": 2,
                "title": "Test Anime 2",
                "episode": 10,
                "total_episodes": 24
            }
        ]
        
        formatted_choices = [
            "Test Anime 1 - Episode 5/12",
            "Test Anime 2 - Episode 10/24"
        ]
        
        selection = "Test Anime 1 - Episode 5/12"
        
        result = _get_history_item_by_selection(history, formatted_choices, selection)
        
        assert result["anilist_id"] == 1
        assert result["title"] == "Test Anime 1"

    def test_get_history_item_by_selection_not_found(self):
        """Test getting history item when selection is not found."""
        from fastanime.cli.interactive.menus.watch_history import _get_history_item_by_selection
        
        history = [
            {
                "anilist_id": 1,
                "title": "Test Anime 1",
                "episode": 5,
                "total_episodes": 12
            }
        ]
        
        formatted_choices = ["Test Anime 1 - Episode 5/12"]
        selection = "Non-existent Selection"
        
        result = _get_history_item_by_selection(history, formatted_choices, selection)
        
        assert result is None
