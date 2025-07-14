"""
Tests for the media actions menu functionality.
"""

import pytest
from unittest.mock import Mock, patch

from fastanime.cli.interactive.menus.media_actions import media_actions
from fastanime.cli.interactive.state import ControlFlow, State, MediaApiState, ProviderState
from fastanime.libs.api.types import MediaItem, MediaTitle, MediaTrailer
from fastanime.libs.players.types import PlayerResult


class TestMediaActionsMenu:
    """Test cases for the media actions menu."""

    def test_media_actions_menu_display(self, mock_context, state_with_media_api):
        """Test that media actions menu displays correctly."""
        mock_context.selector.choose.return_value = "🔙 Back to Results"
        
        with patch('fastanime.cli.interactive.menus.media_actions.get_auth_status_indicator') as mock_auth:
            mock_auth.return_value = ("🟢 Authenticated", Mock())
            
            result = media_actions(mock_context, state_with_media_api)
            
            # Should go back when "Back to Results" is selected
            assert result == ControlFlow.BACK
            
            # Verify selector was called with expected options
            mock_context.selector.choose.assert_called_once()
            call_args = mock_context.selector.choose.call_args
            choices = call_args[1]['choices']
            
            # Check that key options are present
            expected_options = [
                "Stream", "Watch Trailer", "Add/Update List", 
                "Score Anime", "Add to Local History", "View Info", "Back to Results"
            ]
            
            for option in expected_options:
                assert any(option in choice for choice in choices)

    def test_media_actions_stream_selection(self, mock_context, state_with_media_api):
        """Test selecting stream from media actions."""
        mock_context.selector.choose.return_value = "▶️ Stream"
        
        with patch('fastanime.cli.interactive.menus.media_actions._stream') as mock_stream:
            mock_action = Mock()
            mock_action.return_value = State(menu_name="PROVIDER_SEARCH")
            mock_stream.return_value = mock_action
            
            result = media_actions(mock_context, state_with_media_api)
            
            # Should call stream function
            mock_stream.assert_called_once_with(mock_context, state_with_media_api)
            # Should return state transition
            assert isinstance(result, State)
            assert result.menu_name == "PROVIDER_SEARCH"

    def test_media_actions_trailer_selection(self, mock_context, state_with_media_api):
        """Test selecting watch trailer from media actions."""
        mock_context.selector.choose.return_value = "📼 Watch Trailer"
        
        with patch('fastanime.cli.interactive.menus.media_actions._watch_trailer') as mock_trailer:
            mock_action = Mock()
            mock_action.return_value = ControlFlow.CONTINUE
            mock_trailer.return_value = mock_action
            
            result = media_actions(mock_context, state_with_media_api)
            
            # Should call trailer function
            mock_trailer.assert_called_once_with(mock_context, state_with_media_api)
            assert result == ControlFlow.CONTINUE

    def test_media_actions_add_to_list_selection(self, mock_context, state_with_media_api):
        """Test selecting add/update list from media actions."""
        mock_context.selector.choose.return_value = "➕ Add/Update List"
        
        with patch('fastanime.cli.interactive.menus.media_actions._add_to_list') as mock_add:
            mock_action = Mock()
            mock_action.return_value = ControlFlow.CONTINUE
            mock_add.return_value = mock_action
            
            result = media_actions(mock_context, state_with_media_api)
            
            # Should call add to list function
            mock_add.assert_called_once_with(mock_context, state_with_media_api)
            assert result == ControlFlow.CONTINUE

    def test_media_actions_score_selection(self, mock_context, state_with_media_api):
        """Test selecting score anime from media actions."""
        mock_context.selector.choose.return_value = "⭐ Score Anime"
        
        with patch('fastanime.cli.interactive.menus.media_actions._score_anime') as mock_score:
            mock_action = Mock()
            mock_action.return_value = ControlFlow.CONTINUE
            mock_score.return_value = mock_action
            
            result = media_actions(mock_context, state_with_media_api)
            
            # Should call score function
            mock_score.assert_called_once_with(mock_context, state_with_media_api)
            assert result == ControlFlow.CONTINUE

    def test_media_actions_local_history_selection(self, mock_context, state_with_media_api):
        """Test selecting add to local history from media actions."""
        mock_context.selector.choose.return_value = "📚 Add to Local History"
        
        with patch('fastanime.cli.interactive.menus.media_actions._add_to_local_history') as mock_history:
            mock_action = Mock()
            mock_action.return_value = ControlFlow.CONTINUE
            mock_history.return_value = mock_action
            
            result = media_actions(mock_context, state_with_media_api)
            
            # Should call local history function
            mock_history.assert_called_once_with(mock_context, state_with_media_api)
            assert result == ControlFlow.CONTINUE

    def test_media_actions_view_info_selection(self, mock_context, state_with_media_api):
        """Test selecting view info from media actions."""
        mock_context.selector.choose.return_value = "ℹ️ View Info"
        
        with patch('fastanime.cli.interactive.menus.media_actions._view_info') as mock_info:
            mock_action = Mock()
            mock_action.return_value = ControlFlow.CONTINUE
            mock_info.return_value = mock_action
            
            result = media_actions(mock_context, state_with_media_api)
            
            # Should call view info function
            mock_info.assert_called_once_with(mock_context, state_with_media_api)
            assert result == ControlFlow.CONTINUE

    def test_media_actions_back_selection(self, mock_context, state_with_media_api):
        """Test selecting back from media actions."""
        mock_context.selector.choose.return_value = "🔙 Back to Results"
        
        with patch('fastanime.cli.interactive.menus.media_actions.get_auth_status_indicator') as mock_auth:
            mock_auth.return_value = ("Auth Status", Mock())
            
            result = media_actions(mock_context, state_with_media_api)
            
            assert result == ControlFlow.BACK

    def test_media_actions_no_choice(self, mock_context, state_with_media_api):
        """Test media actions menu when no choice is made."""
        mock_context.selector.choose.return_value = None
        
        with patch('fastanime.cli.interactive.menus.media_actions.get_auth_status_indicator') as mock_auth:
            mock_auth.return_value = ("Auth Status", Mock())
            
            result = media_actions(mock_context, state_with_media_api)
            
            # Should return BACK when no choice is made
            assert result == ControlFlow.BACK

    def test_media_actions_unknown_choice(self, mock_context, state_with_media_api):
        """Test media actions menu with unknown choice."""
        mock_context.selector.choose.return_value = "Unknown Option"
        
        with patch('fastanime.cli.interactive.menus.media_actions.get_auth_status_indicator') as mock_auth:
            mock_auth.return_value = ("Auth Status", Mock())
            
            result = media_actions(mock_context, state_with_media_api)
            
            # Should return BACK for unknown choices
            assert result == ControlFlow.BACK

    def test_media_actions_header_content(self, mock_context, state_with_media_api):
        """Test that media actions header contains anime title and auth status."""
        mock_context.selector.choose.return_value = "🔙 Back to Results"
        
        with patch('fastanime.cli.interactive.menus.media_actions.get_auth_status_indicator') as mock_auth:
            mock_auth.return_value = ("🟢 Authenticated", Mock())
            
            result = media_actions(mock_context, state_with_media_api)
            
            # Verify header contains anime title and auth status
            call_args = mock_context.selector.choose.call_args
            header = call_args[1]['header']
            assert "Test Anime" in header
            assert "🟢 Authenticated" in header

    def test_media_actions_icons_enabled(self, mock_context, state_with_media_api):
        """Test media actions menu with icons enabled."""
        mock_context.config.general.icons = True
        mock_context.selector.choose.return_value = "▶️ Stream"
        
        with patch('fastanime.cli.interactive.menus.media_actions._stream') as mock_stream:
            mock_action = Mock()
            mock_action.return_value = State(menu_name="PROVIDER_SEARCH")
            mock_stream.return_value = mock_action
            
            result = media_actions(mock_context, state_with_media_api)
            
            # Should work with icons enabled
            assert isinstance(result, State)
            assert result.menu_name == "PROVIDER_SEARCH"

    def test_media_actions_icons_disabled(self, mock_context, state_with_media_api):
        """Test media actions menu with icons disabled."""
        mock_context.config.general.icons = False
        mock_context.selector.choose.return_value = "Stream"
        
        with patch('fastanime.cli.interactive.menus.media_actions._stream') as mock_stream:
            mock_action = Mock()
            mock_action.return_value = State(menu_name="PROVIDER_SEARCH")
            mock_stream.return_value = mock_action
            
            result = media_actions(mock_context, state_with_media_api)
            
            # Should work with icons disabled
            assert isinstance(result, State)
            assert result.menu_name == "PROVIDER_SEARCH"


class TestMediaActionsHelperFunctions:
    """Test the helper functions in media actions menu."""

    def test_stream_function(self, mock_context, state_with_media_api):
        """Test the stream helper function."""
        from fastanime.cli.interactive.menus.media_actions import _stream
        
        stream_func = _stream(mock_context, state_with_media_api)
        
        # Should return a function that transitions to PROVIDER_SEARCH
        result = stream_func()
        assert isinstance(result, State)
        assert result.menu_name == "PROVIDER_SEARCH"
        # Should preserve media API state
        assert result.media_api.anime == state_with_media_api.media_api.anime

    def test_watch_trailer_success(self, mock_context, state_with_media_api):
        """Test watching trailer successfully."""
        from fastanime.cli.interactive.menus.media_actions import _watch_trailer
        
        # Mock anime with trailer URL
        anime_with_trailer = MediaItem(
            id=1,
            title=MediaTitle(english="Test Anime", romaji="Test Anime"),
            status="FINISHED",
            episodes=12,
            trailer=MediaTrailer(id="test", site="youtube")
        )
        
        state_with_trailer = State(
            menu_name="MEDIA_ACTIONS",
            media_api=MediaApiState(anime=anime_with_trailer)
        )
        
        trailer_func = _watch_trailer(mock_context, state_with_trailer)
        
        # Mock successful player result
        mock_context.player.play.return_value = PlayerResult()
        
        with patch('fastanime.cli.interactive.menus.media_actions.create_feedback_manager') as mock_feedback:
            feedback_obj = Mock()
            mock_feedback.return_value = feedback_obj
            
            result = trailer_func()
            
            # Should play trailer and continue
            mock_context.player.play.assert_called_once()
            assert result == ControlFlow.CONTINUE

    def test_watch_trailer_no_url(self, mock_context, state_with_media_api):
        """Test watching trailer when no trailer URL available."""
        from fastanime.cli.interactive.menus.media_actions import _watch_trailer
        
        trailer_func = _watch_trailer(mock_context, state_with_media_api)
        
        with patch('fastanime.cli.interactive.menus.media_actions.create_feedback_manager') as mock_feedback:
            feedback_obj = Mock()
            mock_feedback.return_value = feedback_obj
            
            result = trailer_func()
            
            # Should show warning and continue
            feedback_obj.warning.assert_called_once()
            assert result == ControlFlow.CONTINUE

    def test_add_to_list_authenticated(self, mock_context, state_with_media_api):
        """Test adding to list when authenticated."""
        from fastanime.cli.interactive.menus.media_actions import _add_to_list
        
        add_func = _add_to_list(mock_context, state_with_media_api)
        
        # Mock authentication check
        with patch('fastanime.cli.interactive.menus.media_actions.check_authentication_required') as mock_auth:
            mock_auth.return_value = True
            
            # Mock status selection
            mock_context.selector.choose.return_value = "CURRENT"
            
            # Mock successful API call
            with patch('fastanime.cli.interactive.menus.media_actions.execute_with_feedback') as mock_execute:
                mock_execute.return_value = (True, None)
                
                result = add_func()
                
                # Should call API and continue
                mock_execute.assert_called_once()
                assert result == ControlFlow.CONTINUE

    def test_add_to_list_not_authenticated(self, mock_context, state_with_media_api):
        """Test adding to list when not authenticated."""
        from fastanime.cli.interactive.menus.media_actions import _add_to_list
        
        add_func = _add_to_list(mock_context, state_with_media_api)
        
        # Mock authentication check failure
        with patch('fastanime.cli.interactive.menus.media_actions.check_authentication_required') as mock_auth:
            mock_auth.return_value = False
            
            result = add_func()
            
            # Should continue without API call
            assert result == ControlFlow.CONTINUE

    def test_score_anime_authenticated(self, mock_context, state_with_media_api):
        """Test scoring anime when authenticated."""
        from fastanime.cli.interactive.menus.media_actions import _score_anime
        
        score_func = _score_anime(mock_context, state_with_media_api)
        
        # Mock authentication check
        with patch('fastanime.cli.interactive.menus.media_actions.check_authentication_required') as mock_auth:
            mock_auth.return_value = True
            
            # Mock score input
            mock_context.selector.ask.return_value = "8.5"
            
            # Mock successful API call
            with patch('fastanime.cli.interactive.menus.media_actions.execute_with_feedback') as mock_execute:
                mock_execute.return_value = (True, None)
                
                result = score_func()
                
                # Should call API and continue
                mock_execute.assert_called_once()
                assert result == ControlFlow.CONTINUE

    def test_score_anime_invalid_score(self, mock_context, state_with_media_api):
        """Test scoring anime with invalid score."""
        from fastanime.cli.interactive.menus.media_actions import _score_anime
        
        score_func = _score_anime(mock_context, state_with_media_api)
        
        # Mock authentication check
        with patch('fastanime.cli.interactive.menus.media_actions.check_authentication_required') as mock_auth:
            mock_auth.return_value = True
            
            # Mock invalid score input
            mock_context.selector.ask.return_value = "invalid"
            
            with patch('fastanime.cli.interactive.menus.media_actions.create_feedback_manager') as mock_feedback:
                feedback_obj = Mock()
                mock_feedback.return_value = feedback_obj
                
                result = score_func()
                
                # Should show error and continue
                feedback_obj.error.assert_called_once()
                assert result == ControlFlow.CONTINUE

    def test_add_to_local_history(self, mock_context, state_with_media_api):
        """Test adding anime to local history."""
        from fastanime.cli.interactive.menus.media_actions import _add_to_local_history
        
        history_func = _add_to_local_history(mock_context, state_with_media_api)
        
        with patch('fastanime.cli.utils.watch_history_tracker.watch_tracker') as mock_tracker:
            mock_tracker.add_anime_to_history.return_value = True
            mock_context.selector.choose.return_value = "Watching"
            mock_context.selector.ask.return_value = "5"
            
            with patch('fastanime.cli.utils.watch_history_manager.WatchHistoryManager') as mock_history_manager:
                mock_manager_instance = Mock()
                mock_history_manager.return_value = mock_manager_instance
                mock_manager_instance.get_entry.return_value = None
                
                with patch('fastanime.cli.interactive.menus.media_actions.create_feedback_manager') as mock_feedback:
                    feedback_obj = Mock()
                    mock_feedback.return_value = feedback_obj
                    
                    result = history_func()
                    
                    # Should add to history successfully
                    mock_tracker.add_anime_to_history.assert_called_once()
                    feedback_obj.success.assert_called_once()
                    assert result == ControlFlow.CONTINUE

    def test_view_info(self, mock_context, state_with_media_api):
        """Test viewing anime information."""
        from fastanime.cli.interactive.menus.media_actions import _view_info
        
        info_func = _view_info(mock_context, state_with_media_api)
        
        with patch('fastanime.cli.interactive.menus.media_actions.Console') as mock_console:
            mock_context.selector.ask.return_value = ""
            
            result = info_func()
            
            # Should create console and display info
            mock_console.assert_called_once()
            # Should ask user to continue
            mock_context.selector.ask.assert_called_once_with("Press Enter to continue...")
            assert result == ControlFlow.CONTINUE
