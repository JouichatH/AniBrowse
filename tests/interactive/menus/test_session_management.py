"""
Tests for the session management menu functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime

from fastanime.cli.interactive.menus.session_management import session_management
from fastanime.cli.interactive.state import ControlFlow, State


class TestSessionManagementMenu:
    """Test cases for the session management menu."""

    def test_session_management_menu_display(self, mock_context, empty_state):
        """Test that session management menu displays correctly."""
        mock_context.selector.choose.return_value = "🔙 Back to Main Menu"
        
        result = session_management(mock_context, empty_state)
        
        # Should go back when "Back to Main Menu" is selected
        assert result == ControlFlow.BACK
        
        # Verify selector was called with expected options
        mock_context.selector.choose.assert_called_once()
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        
        # Check that key options are present
        expected_options = [
            "Save Session", "Load Session", "List Saved Sessions",
            "Delete Session", "Session Statistics", "Auto-save Settings",
            "Back to Main Menu"
        ]
        
        for option in expected_options:
            assert any(option in choice for choice in choices)

    def test_session_management_save_session(self, mock_context, empty_state):
        """Test saving a session."""
        mock_context.selector.choose.return_value = "💾 Save Session"
        mock_context.selector.ask.side_effect = ["test_session", "Test session description"]
        
        with patch('fastanime.cli.interactive.menus.session_management.session') as mock_session:
            mock_session.save.return_value = True
            
            result = session_management(mock_context, empty_state)
            
            # Should save session and continue
            mock_session.save.assert_called_once()
            assert result == ControlFlow.CONTINUE

    def test_session_management_save_session_cancelled(self, mock_context, empty_state):
        """Test saving a session when cancelled."""
        mock_context.selector.choose.return_value = "💾 Save Session"
        mock_context.selector.ask.return_value = ""  # Empty session name
        
        result = session_management(mock_context, empty_state)
        
        # Should continue without saving
        assert result == ControlFlow.CONTINUE

    def test_session_management_load_session(self, mock_context, empty_state):
        """Test loading a session."""
        mock_context.selector.choose.return_value = "📂 Load Session"
        
        # Mock available sessions
        mock_sessions = [
            {"name": "session1.json", "created": "2023-01-01", "size": "1.2KB"},
            {"name": "session2.json", "created": "2023-01-02", "size": "1.5KB"}
        ]
        
        mock_context.selector.choose.side_effect = [
            "📂 Load Session",
            "session1.json"
        ]
        
        with patch('fastanime.cli.interactive.menus.session_management.session') as mock_session:
            mock_session.list_saved_sessions.return_value = mock_sessions
            mock_session.resume.return_value = True
            
            result = session_management(mock_context, empty_state)
            
            # Should load session and reload config
            mock_session.resume.assert_called_once()
            assert result == ControlFlow.RELOAD_CONFIG

    def test_session_management_load_session_no_sessions(self, mock_context, empty_state):
        """Test loading a session when no sessions exist."""
        mock_context.selector.choose.return_value = "📂 Load Session"
        
        with patch('fastanime.cli.interactive.menus.session_management.session') as mock_session:
            mock_session.list_saved_sessions.return_value = []
            
            with patch('fastanime.cli.interactive.menus.session_management.create_feedback_manager') as mock_feedback:
                feedback_obj = Mock()
                mock_feedback.return_value = feedback_obj
                
                result = session_management(mock_context, empty_state)
                
                # Should show info message and continue
                feedback_obj.info.assert_called_once()
                assert result == ControlFlow.CONTINUE

    def test_session_management_load_session_cancelled(self, mock_context, empty_state):
        """Test loading a session when selection is cancelled."""
        mock_context.selector.choose.side_effect = [
            "📂 Load Session",
            None  # Cancelled selection
        ]
        
        with patch('fastanime.cli.interactive.menus.session_management.session') as mock_session:
            mock_session.list_saved_sessions.return_value = [
                {"name": "session1.json", "created": "2023-01-01", "size": "1.2KB"}
            ]
            
            result = session_management(mock_context, empty_state)
            
            # Should continue without loading
            assert result == ControlFlow.CONTINUE

    def test_session_management_list_sessions(self, mock_context, empty_state):
        """Test listing saved sessions."""
        mock_context.selector.choose.return_value = "📋 List Saved Sessions"
        
        mock_sessions = [
            {
                "name": "session1.json",
                "created": "2023-01-01 12:00:00",
                "size": "1.2KB",
                "session_name": "Test Session 1",
                "description": "Test description 1"
            },
            {
                "name": "session2.json",
                "created": "2023-01-02 13:00:00",
                "size": "1.5KB",
                "session_name": "Test Session 2",
                "description": "Test description 2"
            }
        ]
        
        with patch('fastanime.cli.interactive.menus.session_management.session') as mock_session:
            mock_session.list_saved_sessions.return_value = mock_sessions
            
            with patch('fastanime.cli.interactive.menus.session_management.create_feedback_manager') as mock_feedback:
                feedback_obj = Mock()
                mock_feedback.return_value = feedback_obj
                
                result = session_management(mock_context, empty_state)
                
                # Should display session list and pause
                feedback_obj.pause_for_user.assert_called_once()
                assert result == ControlFlow.CONTINUE

    def test_session_management_list_sessions_empty(self, mock_context, empty_state):
        """Test listing sessions when none exist."""
        mock_context.selector.choose.return_value = "📋 List Saved Sessions"
        
        with patch('fastanime.cli.interactive.menus.session_management.session') as mock_session:
            mock_session.list_saved_sessions.return_value = []
            
            with patch('fastanime.cli.interactive.menus.session_management.create_feedback_manager') as mock_feedback:
                feedback_obj = Mock()
                mock_feedback.return_value = feedback_obj
                
                result = session_management(mock_context, empty_state)
                
                # Should show info message
                feedback_obj.info.assert_called_once()
                assert result == ControlFlow.CONTINUE

    def test_session_management_delete_session(self, mock_context, empty_state):
        """Test deleting a session."""
        mock_context.selector.choose.side_effect = [
            "🗑️ Delete Session",
            "session1.json"
        ]
        
        mock_sessions = [
            {"name": "session1.json", "created": "2023-01-01", "size": "1.2KB"}
        ]
        
        with patch('fastanime.cli.interactive.menus.session_management.session') as mock_session:
            mock_session.list_saved_sessions.return_value = mock_sessions
            
            with patch('fastanime.cli.interactive.menus.session_management.create_feedback_manager') as mock_feedback:
                feedback_obj = Mock()
                feedback_obj.confirm.return_value = True
                mock_feedback.return_value = feedback_obj
                
                with patch('fastanime.cli.interactive.menus.session_management.Path.unlink') as mock_unlink:
                    result = session_management(mock_context, empty_state)
                    
                    # Should delete session file
                    mock_unlink.assert_called_once()
                    feedback_obj.success.assert_called_once()
                    assert result == ControlFlow.CONTINUE

    def test_session_management_delete_session_cancelled(self, mock_context, empty_state):
        """Test deleting a session when cancelled."""
        mock_context.selector.choose.side_effect = [
            "🗑️ Delete Session",
            "session1.json"
        ]
        
        mock_sessions = [
            {"name": "session1.json", "created": "2023-01-01", "size": "1.2KB"}
        ]
        
        with patch('fastanime.cli.interactive.menus.session_management.session') as mock_session:
            mock_session.list_saved_sessions.return_value = mock_sessions
            
            with patch('fastanime.cli.interactive.menus.session_management.create_feedback_manager') as mock_feedback:
                feedback_obj = Mock()
                feedback_obj.confirm.return_value = False  # User cancels deletion
                mock_feedback.return_value = feedback_obj
                
                result = session_management(mock_context, empty_state)
                
                # Should not delete and continue
                assert result == ControlFlow.CONTINUE

    def test_session_management_session_statistics(self, mock_context, empty_state):
        """Test viewing session statistics."""
        mock_context.selector.choose.return_value = "📊 Session Statistics"
        
        mock_stats = {
            "current_states": 5,
            "current_menu": "MAIN",
            "auto_save_enabled": True,
            "has_auto_save": False,
            "has_crash_backup": False
        }
        
        with patch('fastanime.cli.interactive.menus.session_management.session') as mock_session:
            mock_session.get_session_stats.return_value = mock_stats
            
            with patch('fastanime.cli.interactive.menus.session_management.create_feedback_manager') as mock_feedback:
                feedback_obj = Mock()
                mock_feedback.return_value = feedback_obj
                
                result = session_management(mock_context, empty_state)
                
                # Should display stats and pause
                feedback_obj.pause_for_user.assert_called_once()
                assert result == ControlFlow.CONTINUE

    def test_session_management_toggle_auto_save(self, mock_context, empty_state):
        """Test toggling auto-save settings."""
        mock_context.selector.choose.return_value = "⚙️ Auto-save Settings"
        
        with patch('fastanime.cli.interactive.menus.session_management.session') as mock_session:
            mock_session.get_session_stats.return_value = {"auto_save_enabled": True}
            
            with patch('fastanime.cli.interactive.menus.session_management.create_feedback_manager') as mock_feedback:
                feedback_obj = Mock()
                feedback_obj.confirm.return_value = True
                mock_feedback.return_value = feedback_obj
                
                result = session_management(mock_context, empty_state)
                
                # Should toggle auto-save
                mock_session.enable_auto_save.assert_called_once()
                assert result == ControlFlow.CONTINUE

    def test_session_management_cleanup_old_sessions(self, mock_context, empty_state):
        """Test cleaning up old sessions."""
        mock_context.selector.choose.return_value = "🧹 Cleanup Old Sessions"
        
        with patch('fastanime.cli.interactive.menus.session_management.session') as mock_session:
            mock_session.cleanup_old_sessions.return_value = 3  # 3 sessions cleaned
            
            with patch('fastanime.cli.interactive.menus.session_management.create_feedback_manager') as mock_feedback:
                feedback_obj = Mock()
                feedback_obj.confirm.return_value = True
                mock_feedback.return_value = feedback_obj
                
                result = session_management(mock_context, empty_state)
                
                # Should cleanup and show success
                mock_session.cleanup_old_sessions.assert_called_once()
                feedback_obj.success.assert_called_once()
                assert result == ControlFlow.CONTINUE

    def test_session_management_create_backup(self, mock_context, empty_state):
        """Test creating manual backup."""
        mock_context.selector.choose.return_value = "💾 Create Manual Backup"
        mock_context.selector.ask.return_value = "my_backup"
        
        with patch('fastanime.cli.interactive.menus.session_management.session') as mock_session:
            mock_session.create_manual_backup.return_value = True
            
            result = session_management(mock_context, empty_state)
            
            # Should create backup
            mock_session.create_manual_backup.assert_called_once_with("my_backup")
            assert result == ControlFlow.CONTINUE

    def test_session_management_back_selection(self, mock_context, empty_state):
        """Test selecting back from session management."""
        mock_context.selector.choose.return_value = "🔙 Back to Main Menu"
        
        result = session_management(mock_context, empty_state)
        
        assert result == ControlFlow.BACK

    def test_session_management_no_choice(self, mock_context, empty_state):
        """Test session management when no choice is made."""
        mock_context.selector.choose.return_value = None
        
        result = session_management(mock_context, empty_state)
        
        # Should go back when no choice is made
        assert result == ControlFlow.BACK

    def test_session_management_icons_enabled(self, mock_context, empty_state):
        """Test session management menu with icons enabled."""
        mock_context.config.general.icons = True
        mock_context.selector.choose.return_value = "🔙 Back to Main Menu"
        
        result = session_management(mock_context, empty_state)
        
        # Should work with icons enabled
        assert result == ControlFlow.BACK

    def test_session_management_icons_disabled(self, mock_context, empty_state):
        """Test session management menu with icons disabled."""
        mock_context.config.general.icons = False
        mock_context.selector.choose.return_value = "Back to Main Menu"
        
        result = session_management(mock_context, empty_state)
        
        # Should work with icons disabled
        assert result == ControlFlow.BACK


class TestSessionManagementHelperFunctions:
    """Test the helper functions in session management menu."""

    def test_format_session_info(self):
        """Test formatting session information for display."""
        from fastanime.cli.interactive.menus.session_management import _format_session_info
        
        session_info = {
            "name": "test_session.json",
            "created": "2023-01-01 12:00:00",
            "size": "1.2KB",
            "session_name": "Test Session",
            "description": "Test description"
        }
        
        result = _format_session_info(session_info, True)  # With icons
        
        assert "Test Session" in result
        assert "test_session.json" in result
        assert "2023-01-01" in result

    def test_format_session_info_no_icons(self):
        """Test formatting session information without icons."""
        from fastanime.cli.interactive.menus.session_management import _format_session_info
        
        session_info = {
            "name": "test_session.json",
            "created": "2023-01-01 12:00:00",
            "size": "1.2KB",
            "session_name": "Test Session",
            "description": "Test description"
        }
        
        result = _format_session_info(session_info, False)  # Without icons
        
        assert "Test Session" in result
        assert "📁" not in result  # No icons should be present

    def test_display_session_statistics(self):
        """Test displaying session statistics."""
        from fastanime.cli.interactive.menus.session_management import _display_session_statistics
        
        console = Mock()
        stats = {
            "current_states": 5,
            "current_menu": "MAIN",
            "auto_save_enabled": True,
            "has_auto_save": False,
            "has_crash_backup": False
        }
        
        _display_session_statistics(console, stats, True)
        
        # Should print table with statistics
        console.print.assert_called()

    def test_get_session_file_path(self):
        """Test getting session file path."""
        from fastanime.cli.interactive.menus.session_management import _get_session_file_path
        
        session_name = "test_session"
        
        result = _get_session_file_path(session_name)
        
        assert isinstance(result, Path)
        assert result.name == "test_session.json"

    def test_validate_session_name_valid(self):
        """Test validating valid session name."""
        from fastanime.cli.interactive.menus.session_management import _validate_session_name
        
        result = _validate_session_name("valid_session_name")
        
        assert result is True

    def test_validate_session_name_invalid(self):
        """Test validating invalid session name."""
        from fastanime.cli.interactive.menus.session_management import _validate_session_name
        
        # Test with invalid characters
        result = _validate_session_name("invalid/session:name")
        
        assert result is False

    def test_validate_session_name_empty(self):
        """Test validating empty session name."""
        from fastanime.cli.interactive.menus.session_management import _validate_session_name
        
        result = _validate_session_name("")
        
        assert result is False

    def test_confirm_session_deletion(self, mock_context):
        """Test confirming session deletion."""
        from fastanime.cli.interactive.menus.session_management import _confirm_session_deletion
        
        session_name = "test_session.json"
        
        with patch('fastanime.cli.interactive.menus.session_management.create_feedback_manager') as mock_feedback:
            feedback_obj = Mock()
            feedback_obj.confirm.return_value = True
            mock_feedback.return_value = feedback_obj
            
            result = _confirm_session_deletion(session_name, True)
            
            # Should confirm deletion
            feedback_obj.confirm.assert_called_once()
            assert result is True

    def test_confirm_session_deletion_cancelled(self, mock_context):
        """Test confirming session deletion when cancelled."""
        from fastanime.cli.interactive.menus.session_management import _confirm_session_deletion
        
        session_name = "test_session.json"
        
        with patch('fastanime.cli.interactive.menus.session_management.create_feedback_manager') as mock_feedback:
            feedback_obj = Mock()
            feedback_obj.confirm.return_value = False
            mock_feedback.return_value = feedback_obj
            
            result = _confirm_session_deletion(session_name, True)
            
            # Should not confirm deletion
            assert result is False
