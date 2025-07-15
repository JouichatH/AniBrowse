"""
Tests for the session management menu.
Tests saving, loading, and managing session state.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from datetime import datetime

from fastanime.cli.interactive.menus.session_management import session_management
from fastanime.cli.interactive.state import State, ControlFlow

from .base_test import BaseMenuTest, SessionMenuTestMixin


class TestSessionManagementMenu(BaseMenuTest, SessionMenuTestMixin):
    """Test cases for the session management menu."""
    
    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager."""
        return self.setup_session_manager_mock()
    
    def test_session_menu_no_choice_goes_back(self, mock_context, basic_state):
        """Test that no choice selected results in BACK."""
        self.setup_selector_choice(mock_context, None)
        
        result = session_management(mock_context, basic_state)
        
        self.assert_back_behavior(result)
        self.assert_console_cleared()
    
    def test_session_menu_back_choice(self, mock_context, basic_state):
        """Test explicit back choice."""
        self.setup_selector_choice(mock_context, "↩️ Back to Main Menu")
        
        result = session_management(mock_context, basic_state)
        
        self.assert_back_behavior(result)
        self.assert_console_cleared()
    
    def test_session_menu_save_session_success(self, mock_context, basic_state):
        """Test successful session save."""
        self.setup_selector_choice(mock_context, "💾 Save Current Session")
        self.setup_selector_input(mock_context, "test_session")
        
        with patch('fastanime.cli.interactive.session.session') as mock_session:
            mock_session.save.return_value = True
            
            result = session_management(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            
            # Verify session save was attempted
            mock_session.save.assert_called_once()
            self.assert_feedback_success_called("Session saved")
    
    def test_session_menu_save_session_failure(self, mock_context, basic_state):
        """Test failed session save."""
        self.setup_selector_choice(mock_context, "💾 Save Current Session")
        self.setup_selector_input(mock_context, "test_session")
        
        with patch('fastanime.cli.interactive.session.session') as mock_session:
            mock_session.save.return_value = False
            
            result = session_management(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            self.assert_feedback_error_called("Failed to save session")
    
    def test_session_menu_save_session_empty_name(self, mock_context, basic_state):
        """Test session save with empty name."""
        self.setup_selector_choice(mock_context, "💾 Save Current Session")
        self.setup_selector_input(mock_context, "")  # Empty name
        
        result = session_management(mock_context, basic_state)
        
        self.assert_continue_behavior(result)
        self.assert_console_cleared()
        self.assert_feedback_warning_called("Session name cannot be empty")
    
    def test_session_menu_load_session_success(self, mock_context, basic_state):
        """Test successful session load."""
        # Mock available sessions
        mock_sessions = [
            {"name": "session1", "file": "session1.json", "created": "2024-01-01"},
            {"name": "session2", "file": "session2.json", "created": "2024-01-02"}
        ]
        
        self.setup_selector_choice(mock_context, "📂 Load Saved Session")
        
        with patch('fastanime.cli.interactive.session.session') as mock_session:
            mock_session.list_saved_sessions.return_value = mock_sessions
            mock_session.resume.return_value = True
            
            # Mock user selecting a session
            with patch.object(mock_context.selector, 'choose', side_effect=["session1"]):
                result = session_management(mock_context, basic_state)
                
                self.assert_continue_behavior(result)
                self.assert_console_cleared()
                
                mock_session.list_saved_sessions.assert_called_once()
                mock_session.resume.assert_called_once()
                self.assert_feedback_success_called("Session loaded")
    
    def test_session_menu_load_session_no_sessions(self, mock_context, basic_state):
        """Test load session with no saved sessions."""
        self.setup_selector_choice(mock_context, "📂 Load Saved Session")
        
        with patch('fastanime.cli.interactive.session.session') as mock_session:
            mock_session.list_saved_sessions.return_value = []
            
            result = session_management(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            self.assert_feedback_info_called("No saved sessions found")
    
    def test_session_menu_load_session_failure(self, mock_context, basic_state):
        """Test failed session load."""
        mock_sessions = [{"name": "session1", "file": "session1.json"}]
        
        self.setup_selector_choice(mock_context, "📂 Load Saved Session")
        
        with patch('fastanime.cli.interactive.session.session') as mock_session:
            mock_session.list_saved_sessions.return_value = mock_sessions
            mock_session.resume.return_value = False
            
            # Mock user selecting a session
            with patch.object(mock_context.selector, 'choose', side_effect=["session1"]):
                result = session_management(mock_context, basic_state)
                
                self.assert_continue_behavior(result)
                self.assert_console_cleared()
                self.assert_feedback_error_called("Failed to load session")
    
    def test_session_menu_delete_session_success(self, mock_context, basic_state):
        """Test successful session deletion."""
        mock_sessions = [{"name": "session1", "file": "session1.json"}]
        
        self.setup_selector_choice(mock_context, "🗑️ Delete Saved Session")
        self.setup_feedback_confirm(True)  # Confirm deletion
        
        with patch('fastanime.cli.interactive.session.session') as mock_session:
            mock_session.list_saved_sessions.return_value = mock_sessions
            
            with patch.object(mock_context.selector, 'choose', side_effect=["session1"]):
                with self.setup_path_exists_mock(True):
                    with patch('pathlib.Path.unlink') as mock_unlink:
                        result = session_management(mock_context, basic_state)
                        
                        self.assert_continue_behavior(result)
                        self.assert_console_cleared()
                        
                        mock_unlink.assert_called_once()
                        self.assert_feedback_success_called("Session deleted")
    
    def test_session_menu_delete_session_cancelled(self, mock_context, basic_state):
        """Test cancelled session deletion."""
        mock_sessions = [{"name": "session1", "file": "session1.json"}]
        
        self.setup_selector_choice(mock_context, "🗑️ Delete Saved Session")
        self.setup_feedback_confirm(False)  # Cancel deletion
        
        with patch('fastanime.cli.interactive.session.session') as mock_session:
            mock_session.list_saved_sessions.return_value = mock_sessions
            
            with patch.object(mock_context.selector, 'choose', side_effect=["session1"]):
                with patch('pathlib.Path.unlink') as mock_unlink:
                    result = session_management(mock_context, basic_state)
                    
                    self.assert_continue_behavior(result)
                    self.assert_console_cleared()
                    
                    mock_unlink.assert_not_called()
                    self.assert_feedback_info_called("Deletion cancelled")
    
    def test_session_menu_cleanup_old_sessions(self, mock_context, basic_state):
        """Test cleanup of old sessions."""
        self.setup_selector_choice(mock_context, "🧹 Cleanup Old Sessions")
        self.setup_feedback_confirm(True)  # Confirm cleanup
        
        with patch('fastanime.cli.interactive.session.session') as mock_session:
            mock_session.cleanup_old_sessions.return_value = 5  # 5 sessions cleaned
            
            result = session_management(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            
            mock_session.cleanup_old_sessions.assert_called_once()
            self.assert_feedback_success_called("Cleaned up 5 old sessions")
    
    def test_session_menu_cleanup_cancelled(self, mock_context, basic_state):
        """Test cancelled cleanup."""
        self.setup_selector_choice(mock_context, "🧹 Cleanup Old Sessions")
        self.setup_feedback_confirm(False)  # Cancel cleanup
        
        with patch('fastanime.cli.interactive.session.session') as mock_session:
            result = session_management(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            
            mock_session.cleanup_old_sessions.assert_not_called()
            self.assert_feedback_info_called("Cleanup cancelled")
    
    def test_session_menu_view_session_stats(self, mock_context, basic_state):
        """Test viewing session statistics."""
        self.setup_selector_choice(mock_context, "📊 View Session Statistics")
        
        mock_stats = {
            "current_states": 3,
            "current_menu": "MAIN",
            "auto_save_enabled": True,
            "has_auto_save": False,
            "has_crash_backup": False
        }
        
        with patch('fastanime.cli.interactive.session.session') as mock_session:
            mock_session.get_session_stats.return_value = mock_stats
            
            result = session_management(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            
            mock_session.get_session_stats.assert_called_once()
            self.mock_feedback.pause_for_user.assert_called_once()
    
    def test_session_menu_toggle_auto_save_enable(self, mock_context, basic_state):
        """Test enabling auto-save."""
        self.setup_selector_choice(mock_context, "⚙️ Toggle Auto-Save")
        
        with patch('fastanime.cli.interactive.session.session') as mock_session:
            mock_session._auto_save_enabled = False  # Currently disabled
            
            result = session_management(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            
            mock_session.enable_auto_save.assert_called_once_with(True)
            self.assert_feedback_success_called("Auto-save enabled")
    
    def test_session_menu_toggle_auto_save_disable(self, mock_context, basic_state):
        """Test disabling auto-save."""
        self.setup_selector_choice(mock_context, "⚙️ Toggle Auto-Save")
        
        with patch('fastanime.cli.interactive.session.session') as mock_session:
            mock_session._auto_save_enabled = True  # Currently enabled
            
            result = session_management(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            
            mock_session.enable_auto_save.assert_called_once_with(False)
            self.assert_feedback_success_called("Auto-save disabled")
    
    def test_session_menu_create_manual_backup(self, mock_context, basic_state):
        """Test creating manual backup."""
        self.setup_selector_choice(mock_context, "💿 Create Manual Backup")
        self.setup_selector_input(mock_context, "my_backup")
        
        with patch('fastanime.cli.interactive.session.session') as mock_session:
            mock_session.create_manual_backup.return_value = True
            
            result = session_management(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            
            mock_session.create_manual_backup.assert_called_once_with("my_backup")
            self.assert_feedback_success_called("Manual backup created")
    
    def test_session_menu_create_manual_backup_failure(self, mock_context, basic_state):
        """Test failed manual backup creation."""
        self.setup_selector_choice(mock_context, "💿 Create Manual Backup")
        self.setup_selector_input(mock_context, "my_backup")
        
        with patch('fastanime.cli.interactive.session.session') as mock_session:
            mock_session.create_manual_backup.return_value = False
            
            result = session_management(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_console_cleared()
            self.assert_feedback_error_called("Failed to create backup")
    
    def test_session_menu_icons_disabled(self, mock_context, basic_state):
        """Test menu display with icons disabled."""
        mock_context.config.general.icons = False
        self.setup_selector_choice(mock_context, None)
        
        result = session_management(mock_context, basic_state)
        
        self.assert_back_behavior(result)
        # Verify options don't contain emoji icons
        mock_context.selector.choose.assert_called_once()
        call_args = mock_context.selector.choose.call_args
        choices = call_args[1]['choices']
        
        for choice in choices:
            assert not any(char in choice for char in '💾📂🗑️🧹📊⚙️💿↩️')
    
    def test_session_menu_file_operations_with_invalid_paths(self, mock_context, basic_state):
        """Test handling of invalid file paths during operations."""
        self.setup_selector_choice(mock_context, "🗑️ Delete Saved Session")
        
        # Mock a session with invalid path
        mock_sessions = [{"name": "session1", "file": "/invalid/path/session1.json"}]
        
        with patch('fastanime.cli.interactive.session.session') as mock_session:
            mock_session.list_saved_sessions.return_value = mock_sessions
            
            with patch.object(mock_context.selector, 'choose', side_effect=["session1"]):
                with self.setup_path_exists_mock(False):  # File doesn't exist
                    result = session_management(mock_context, basic_state)
                    
                    self.assert_continue_behavior(result)
                    self.assert_feedback_error_called("Session file not found")
    
    @pytest.mark.parametrize("session_count", [0, 1, 5, 10])
    def test_session_menu_various_session_counts(self, mock_context, basic_state, session_count):
        """Test handling of various numbers of saved sessions."""
        self.setup_selector_choice(mock_context, "📂 Load Saved Session")
        
        # Create mock sessions
        mock_sessions = []
        for i in range(session_count):
            mock_sessions.append({
                "name": f"session{i+1}",
                "file": f"session{i+1}.json",
                "created": f"2024-01-0{i+1 if i < 9 else '10'}"
            })
        
        with patch('fastanime.cli.interactive.session.session') as mock_session:
            mock_session.list_saved_sessions.return_value = mock_sessions
            
            result = session_management(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            
            if session_count == 0:
                self.assert_feedback_info_called("No saved sessions found")
            else:
                # Should display sessions for selection
                mock_context.selector.choose.assert_called()
    
    def test_session_menu_save_with_special_characters(self, mock_context, basic_state):
        """Test session save with special characters in name."""
        self.setup_selector_choice(mock_context, "💾 Save Current Session")
        self.setup_selector_input(mock_context, "test/session:with*special?chars")
        
        with patch('fastanime.cli.interactive.session.session') as mock_session:
            mock_session.save.return_value = True
            
            result = session_management(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            # Should handle special characters appropriately
            mock_session.save.assert_called_once()
    
    def test_session_menu_exception_handling(self, mock_context, basic_state):
        """Test handling of unexpected exceptions."""
        self.setup_selector_choice(mock_context, "💾 Save Current Session")
        self.setup_selector_input(mock_context, "test_session")
        
        with patch('fastanime.cli.interactive.session.session') as mock_session:
            mock_session.save.side_effect = Exception("Unexpected error")
            
            result = session_management(mock_context, basic_state)
            
            self.assert_continue_behavior(result)
            self.assert_feedback_error_called("An error occurred")
